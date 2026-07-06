import hashlib
import ipaddress
import json
import mimetypes
import os
import secrets
import time
from io import BytesIO
from pathlib import Path
from typing import Annotated

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
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MULTIPART_EARLY_REJECT_OVERHEAD_BYTES = 1024 * 1024


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
        commit_message=f"Delete {item['originalName']}",
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

    content = await file.read()
    size = len(content)
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=upload_too_large_error()["detail"])

    original_name = Path(file.filename or "upload.bin").name
    suffix = Path(original_name).suffix
    digest = hashlib.sha256(content + secrets.token_bytes(8)).hexdigest()[:18]
    item_id = f"{int(time.time())}-{digest}"
    stored_name = f"{item_id}{suffix}"
    path_in_repo = f"files/{stored_name}"

    mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    hf_api.upload_file(
        repo_id=DATASET_REPO_ID,
        repo_type="dataset",
        path_in_repo=path_in_repo,
        path_or_fileobj=BytesIO(content),
        commit_message=f"Upload {original_name}",
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

    items = load_index()
    items.append(item)
    save_index(items)
    return public_item(item)


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
    return FileResponse(path, media_type=item["mimeType"], filename=item["originalName"])
