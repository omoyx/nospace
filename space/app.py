import asyncio
import hashlib
import ipaddress
import json
import logging
import mimetypes
import os
import re
import secrets
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError
from pydantic import BaseModel

APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
DATASET_REPO_ID = os.getenv("DATASET_REPO_ID", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
INDEX_PATH = "index.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
MULTIPART_EARLY_REJECT_OVERHEAD_BYTES = 1024 * 1024
SMART_FILENAME_BASE_URL = os.getenv("BAILIAN_OPENCODE_BASE_URL", "").strip()
SMART_FILENAME_API_KEY = os.getenv("BAILIAN_OPENCODE_API_KEY", "").strip()
SMART_FILENAME_MODEL = os.getenv("BAILIAN_OPENCODE_MODEL", "glm-5.2").strip() or "glm-5.2"
SMART_FILENAME_TIMEOUT_SECONDS = int(os.getenv("SMART_FILENAME_TIMEOUT_SECONDS", "30"))
SMART_FILENAME_MAX_TOKENS = int(os.getenv("SMART_FILENAME_MAX_TOKENS", "120"))

logger = logging.getLogger("nospace")
MOJIBAKE_MARKERS = frozenset("ÃÂâæçåèäðÐÑ¤¦¬¯µ•™œž")
ENCODING_REPAIR_PAIRS = (
    ("latin-1", "utf-8"),
    ("cp1252", "utf-8"),
    ("cp437", "utf-8"),
    ("cp437", "gb18030"),
    ("latin-1", "gb18030"),
    ("gb18030", "utf-8"),
)


def parse_invites(raw: str) -> dict[str, dict[str, str]]:
    invites: dict[str, dict[str, str]] = {}
    for entry in raw.split(","):
        parts = [part.strip() for part in entry.split(":")]
        if len(parts) != 3 or not all(parts):
            continue
        code, role, name = parts
        if role not in {"upload", "download"}:
            continue
        invites[code] = {"role": role, "name": name}
    return invites


INVITES = parse_invites(os.getenv("INVITES", "upload-demo:upload:Uploader,read-demo:download:Reader"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(title="NoSpace Storage", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

hf_api = HfApi(token=HF_TOKEN)


class InviteBody(BaseModel):
    invite: str


def upload_too_large_error() -> dict[str, str]:
    return {"detail": f"文件超过 {MAX_UPLOAD_MB} MB"}


def add_cors_origin(request: Request, response: JSONResponse) -> JSONResponse:
    origin = request.headers.get("origin")
    if not origin:
        return response
    if "*" in ALLOWED_ORIGINS:
        response.headers["access-control-allow-origin"] = "*"
    elif origin in ALLOWED_ORIGINS:
        response.headers["access-control-allow-origin"] = origin
    return response


async def spool_upload_to_temp_file(file: UploadFile) -> tuple[Path, int, str]:
    hasher = hashlib.sha256()
    size = 0
    temp_file = tempfile.NamedTemporaryFile(prefix="nospace-upload-", suffix=".tmp", delete=False)
    temp_path = Path(temp_file.name)

    try:
        with temp_file:
            while True:
                chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=upload_too_large_error()["detail"])
                hasher.update(chunk)
                temp_file.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return temp_path, size, hasher.hexdigest()


def safe_upload_name(filename: str | None) -> str:
    normalized = (filename or "upload.bin").replace("\\", "/")
    return Path(normalized).name or "upload.bin"


def filename_repair_candidates(filename: str) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        candidate = unicodedata.normalize("NFC", candidate).strip()
        if candidate and candidate != filename and candidate not in candidates:
            candidates.append(candidate)

    if re.search(r"(?:%[0-9a-fA-F]{2}){2,}", filename):
        add(unquote(filename))

    for source_encoding, target_encoding in ENCODING_REPAIR_PAIRS:
        try:
            add(filename.encode(source_encoding).decode(target_encoding))
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

    return candidates


def filename_garbled_score(filename: str) -> int:
    stem = Path(filename).stem or filename
    score = stem.count("\ufffd") * 6
    score += len(re.findall(r"(?:%[0-9a-fA-F]{2})", stem))
    score += max(0, stem.count("?") - 1) * 2
    score += sum(character in MOJIBAKE_MARKERS for character in stem)
    score += sum("\u2500" <= character <= "\u259f" for character in stem) * 2
    score += sum(unicodedata.category(character) in {"Cc", "Cs", "Co", "Cn"} for character in stem) * 4
    return score


def is_garbled_filename(filename: str) -> bool:
    score = filename_garbled_score(filename)
    if score >= 4:
        return True

    for candidate in filename_repair_candidates(filename):
        has_cjk = bool(re.search(r"[\u3400-\u9fff]", candidate))
        if has_cjk and filename_garbled_score(candidate) < score:
            return True
    return False


def filename_rename_endpoint(base_url: str) -> str:
    value = base_url.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return value + "/chat/completions"
    return value + "/v1/chat/completions"


def call_glm_filename_rename(filename: str, mime_type: str, repair_candidates: list[str]) -> str:
    extension = Path(filename).suffix
    input_payload = {
        "originalFilename": filename,
        "extension": extension,
        "mimeType": mime_type,
        "encodingRepairCandidates": repair_candidates,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是文件名乱码恢复助手。根据原文件名和可逆编码候选，恢复最可信、简洁、自然的文件名。"
                "优先采用可信的编码恢复结果，不翻译正常的品牌、产品名或人名，不虚构文件内容。"
                "若原意无法恢复，使用与 MIME 类型对应的简洁中文通用名。"
                "必须保留给定扩展名，禁止路径、控制字符和说明文字。"
                "只输出合法 JSON，格式为 {\"filename\":\"文件名.ext\"}。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(input_payload, ensure_ascii=False),
        },
    ]
    payload = {
        "model": SMART_FILENAME_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_completion_tokens": SMART_FILENAME_MAX_TOKENS,
        "enable_thinking": False,
    }
    request = urllib.request.Request(
        filename_rename_endpoint(SMART_FILENAME_BASE_URL),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {SMART_FILENAME_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=SMART_FILENAME_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GLM filename rename returned HTTP {error.code}") from error

    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("GLM filename rename returned an empty response")
    return content


def parsed_glm_filename(content: str) -> str | None:
    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    filename = payload.get("filename") if isinstance(payload, dict) else None
    return filename if isinstance(filename, str) else None


def sanitized_display_filename(candidate: str, original_filename: str) -> str | None:
    value = unicodedata.normalize("NFKC", candidate)
    value = "".join(character for character in value if unicodedata.category(character) not in {"Cc", "Cs"})
    value = value.replace("/", "-").replace("\\", "-")
    value = re.sub(r"\s+", " ", value).strip(" .-\"'`")
    original_extension = Path(original_filename).suffix

    if original_extension:
        if value.lower().endswith(original_extension.lower()):
            base = value[: -len(original_extension)]
        else:
            candidate_extension = Path(value).suffix
            base = value[: -len(candidate_extension)] if candidate_extension else value
        base = base.strip(" .-\"'`")
        value = f"{base}{original_extension}"

    if not value or value in {".", ".."}:
        return None

    if len(value) > 160:
        if original_extension:
            base_limit = max(1, 160 - len(original_extension))
            value = f"{value[: -len(original_extension)][:base_limit].rstrip()}{original_extension}"
        else:
            value = value[:160].rstrip()

    if value == original_filename or is_garbled_filename(value):
        return None
    return value


def deterministic_filename_repair(filename: str) -> str | None:
    ranked_candidates = sorted(
        filename_repair_candidates(filename),
        key=lambda candidate: (filename_garbled_score(candidate), len(candidate)),
    )
    for candidate in ranked_candidates:
        sanitized = sanitized_display_filename(candidate, filename)
        if sanitized:
            return sanitized
    return None


async def smart_display_filename(filename: str, mime_type: str) -> tuple[str, str | None]:
    if not is_garbled_filename(filename):
        return filename, None

    repair_candidates = filename_repair_candidates(filename)
    if SMART_FILENAME_BASE_URL and SMART_FILENAME_API_KEY:
        try:
            response = await asyncio.to_thread(
                call_glm_filename_rename,
                filename,
                mime_type,
                repair_candidates,
            )
            model_filename = parsed_glm_filename(response)
            if model_filename:
                sanitized = sanitized_display_filename(model_filename, filename)
                if sanitized:
                    return sanitized, SMART_FILENAME_MODEL
        except Exception as error:
            logger.warning("Smart filename rename failed: %s", type(error).__name__)

    repaired = deterministic_filename_repair(filename)
    if repaired:
        return repaired, "encoding-repair"
    return filename, None


@app.middleware("http")
async def reject_oversized_upload_request(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/assets":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                request_size = int(content_length)
            except ValueError:
                request_size = 0
            if request_size > MAX_UPLOAD_BYTES + MULTIPART_EARLY_REJECT_OVERHEAD_BYTES:
                response = JSONResponse(status_code=413, content=upload_too_large_error())
                return add_cors_origin(request, response)

    return await call_next(request)


def clean_ip(value: str) -> str:
    value = value.strip().strip('"')
    if not value:
        return ""
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    if value.count(":") == 1 and "." in value:
        return value.rsplit(":", 1)[0]
    return value


def parsed_ip(value: str) -> str:
    ip = clean_ip(value)
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return ""


def forwarded_for_ips(value: str) -> list[str]:
    ips: list[str] = []
    for entry in value.split(","):
        for segment in entry.split(";"):
            key, _, raw_candidate = segment.strip().partition("=")
            if key.lower() == "for":
                ip = parsed_ip(raw_candidate)
                if ip:
                    ips.append(ip)
    return ips


def client_ip(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        raw_value = request.headers.get(header)
        if not raw_value:
            continue
        for candidate in raw_value.split(","):
            ip = parsed_ip(candidate)
            if ip:
                return ip

    forwarded = request.headers.get("forwarded")
    if forwarded:
        ips = forwarded_for_ips(forwarded)
        if ips:
            return ips[0]

    if request.client:
        return parsed_ip(request.client.host) or request.client.host
    return "unknown"


def public_session(session: dict[str, str], request: Request) -> dict[str, str]:
    if session["role"] == "upload":
        return {"role": session["role"], "name": client_ip(request)}
    return session


def ensure_dataset() -> None:
    if not DATASET_REPO_ID:
        raise HTTPException(status_code=500, detail="DATASET_REPO_ID 未配置")
    try:
        hf_api.repo_info(repo_id=DATASET_REPO_ID, repo_type="dataset")
    except RepositoryNotFoundError as error:
        raise HTTPException(status_code=500, detail="Dataset 仓库不可用") from error


def load_index() -> list[dict]:
    ensure_dataset()
    try:
        path = hf_hub_download(
            repo_id=DATASET_REPO_ID,
            filename=INDEX_PATH,
            repo_type="dataset",
            token=HF_TOKEN,
        )
    except EntryNotFoundError:
        return []
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail="Dataset index.json 无法解析") from error


def save_index(items: list[dict]) -> None:
    ensure_dataset()
    payload = json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")
    hf_api.upload_file(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
        path_in_repo=INDEX_PATH,
        path_or_fileobj=BytesIO(payload),
        commit_message="Update NoSpace index",
    )


def delete_asset_item(item_id: str, invite: str | None) -> dict[str, str]:
    session = session_for(invite)
    if session["role"] != "upload":
        raise HTTPException(status_code=403, detail="当前邀请码没有删除权限")

    items = load_index()
    item = next((item for item in items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="文件不存在")

    next_items = [item for item in items if item["id"] != item_id]
    payload = json.dumps(next_items, ensure_ascii=False, indent=2).encode("utf-8")
    ensure_dataset()
    hf_api.create_commit(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
        operations=[
            CommitOperationDelete(path_in_repo=file_path(item)),
            CommitOperationAdd(path_in_repo=INDEX_PATH, path_or_fileobj=BytesIO(payload)),
        ],
        commit_message=f"Delete {item.get('displayName') or item['originalName']}",
    )
    return {"ok": "true", "id": item_id}


def session_for(invite: str | None) -> dict[str, str]:
    if not invite or invite not in INVITES:
        raise HTTPException(status_code=401, detail="邀请码无效")
    return INVITES[invite]


def public_item(item: dict) -> dict:
    return {
        **item,
        "url": f"/files/{item['id']}",
        "downloadUrl": f"/files/{item['id']}/download",
    }


def file_path(item: dict) -> str:
    return item.get("path") or f"files/{item['filename']}"


@app.get("/")
def health() -> dict[str, str]:
    return {
        "ok": "true",
        "service": "nospace-storage",
        "storage": "huggingface-dataset" if DATASET_REPO_ID else "unconfigured",
        "smartFilenameRename": SMART_FILENAME_MODEL if SMART_FILENAME_BASE_URL and SMART_FILENAME_API_KEY else "disabled",
    }


@app.post("/api/session")
def create_session(body: InviteBody, request: Request) -> dict[str, str]:
    return public_session(session_for(body.invite), request)


@app.get("/api/assets")
def list_assets(x_invite_code: Annotated[str | None, Header()] = None) -> list[dict]:
    session_for(x_invite_code)
    items = load_index()
    items.sort(key=lambda item: item["uploadedAt"], reverse=True)
    return [public_item(item) for item in items]


@app.post("/api/assets")
async def create_asset(
    request: Request,
    file: Annotated[UploadFile, File()],
    note: Annotated[str, Form()] = "",
    x_invite_code: Annotated[str | None, Header()] = None,
) -> dict:
    session = session_for(x_invite_code)
    if session["role"] != "upload":
        raise HTTPException(status_code=403, detail="当前邀请码没有上传权限")

    ensure_dataset()
    temp_path: Path | None = None

    try:
        temp_path, size, content_hash = await spool_upload_to_temp_file(file)
        original_name = safe_upload_name(file.filename)
        suffix = Path(original_name).suffix
        digest = hashlib.sha256(f"{content_hash}:{secrets.token_hex(8)}".encode("utf-8")).hexdigest()[:18]
        item_id = f"{int(time.time())}-{digest}"
        stored_name = f"{item_id}{suffix}"
        path_in_repo = f"files/{stored_name}"

        mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        display_name, rename_model = await smart_display_filename(original_name, mime_type)
        hf_api.upload_file(
            repo_id=DATASET_REPO_ID,
            repo_type="dataset",
            path_in_repo=path_in_repo,
            path_or_fileobj=temp_path,
            commit_message=f"Upload {display_name}",
        )

        item = {
            "id": item_id,
            "filename": stored_name,
            "path": path_in_repo,
            "originalName": original_name,
            "mimeType": mime_type,
            "size": size,
            "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sourceName": client_ip(request),
            "note": note[:400],
        }
        if display_name != original_name:
            item["displayName"] = display_name
            item["renameModel"] = rename_model

        items = load_index()
        items.append(item)
        save_index(items)
        return public_item(item)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        await file.close()


@app.delete("/api/assets/{item_id}")
def delete_asset(item_id: str, x_invite_code: Annotated[str | None, Header()] = None) -> dict[str, str]:
    return delete_asset_item(item_id, x_invite_code)


def file_item(item_id: str, invite: str | None) -> tuple[dict, Path]:
    session_for(invite)
    for item in load_index():
        if item["id"] == item_id:
            try:
                path = hf_hub_download(
                    repo_id=DATASET_REPO_ID,
                    filename=file_path(item),
                    repo_type="dataset",
                    token=HF_TOKEN,
                )
            except EntryNotFoundError as error:
                raise HTTPException(status_code=404, detail="文件不存在")
            return item, Path(path)
    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/files/{item_id}")
def read_file(item_id: str, invite: Annotated[str | None, Query()] = None) -> FileResponse:
    item, path = file_item(item_id, invite)
    return FileResponse(path, media_type=item["mimeType"])


@app.get("/files/{item_id}/download")
def download_file(item_id: str, invite: Annotated[str | None, Query()] = None) -> FileResponse:
    item, path = file_item(item_id, invite)
    return FileResponse(path, media_type=item["mimeType"], filename=item.get("displayName") or item["originalName"])
