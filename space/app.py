import hashlib
import json
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
DATA_DIR = Path(os.getenv("NOSPACE_DATA_DIR", "/data/nospace"))
FILES_DIR = DATA_DIR / "files"
INDEX_PATH = DATA_DIR / "index.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))


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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class InviteBody(BaseModel):
    invite: str


def ensure_storage() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        INDEX_PATH.write_text("[]", encoding="utf-8")


def load_index() -> list[dict]:
    ensure_storage()
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(items: list[dict]) -> None:
    ensure_storage()
    temporary_path = INDEX_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(INDEX_PATH)


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


@app.get("/")
def health() -> dict[str, str]:
    return {"ok": "true", "service": "nospace-storage"}


@app.post("/api/session")
def create_session(body: InviteBody) -> dict[str, str]:
    return session_for(body.invite)


@app.get("/api/assets")
def list_assets(x_invite_code: Annotated[str | None, Header()] = None) -> list[dict]:
    session_for(x_invite_code)
    items = load_index()
    items.sort(key=lambda item: item["uploadedAt"], reverse=True)
    return [public_item(item) for item in items]


@app.post("/api/assets")
async def create_asset(
    file: Annotated[UploadFile, File()],
    note: Annotated[str, Form()] = "",
    x_invite_code: Annotated[str | None, Header()] = None,
) -> dict:
    session = session_for(x_invite_code)
    if session["role"] != "upload":
        raise HTTPException(status_code=403, detail="当前邀请码没有上传权限")

    content = await file.read()
    size = len(content)
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {MAX_UPLOAD_MB} MB")

    ensure_storage()
    original_name = Path(file.filename or "upload.bin").name
    suffix = Path(original_name).suffix
    digest = hashlib.sha256(content + secrets.token_bytes(8)).hexdigest()[:18]
    item_id = f"{int(time.time())}-{digest}"
    stored_name = f"{item_id}{suffix}"
    stored_path = FILES_DIR / stored_name
    stored_path.write_bytes(content)

    mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    item = {
        "id": item_id,
        "filename": stored_name,
        "originalName": original_name,
        "mimeType": mime_type,
        "size": size,
        "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceName": session["name"],
        "note": note[:400],
    }

    items = load_index()
    items.append(item)
    save_index(items)
    return public_item(item)


def file_item(item_id: str, invite: str | None) -> tuple[dict, Path]:
    session_for(invite)
    for item in load_index():
        if item["id"] == item_id:
            path = FILES_DIR / item["filename"]
            if not path.exists():
                raise HTTPException(status_code=404, detail="文件不存在")
            return item, path
    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/files/{item_id}")
def read_file(item_id: str, invite: Annotated[str | None, Query()] = None) -> FileResponse:
    item, path = file_item(item_id, invite)
    return FileResponse(path, media_type=item["mimeType"])


@app.get("/files/{item_id}/download")
def download_file(item_id: str, invite: Annotated[str | None, Query()] = None) -> FileResponse:
    item, path = file_item(item_id, invite)
    return FileResponse(path, media_type=item["mimeType"], filename=item["originalName"])
