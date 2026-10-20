"""Firm methods. Content is entered locally and is not tied to one project."""

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from deerflow.config.paths import get_paths
from deerflow.utils.file_conversion import convert_file_to_markdown

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["methods"])

_TITLE_LIMIT = 80
_BODY_LIMIT = 2000
_METHOD_LIMIT = 30
_FILE_BYTES = 10 * 1024 * 1024
_EXCERPT_STORE_LIMIT = 20_000
_FILENAME_LIMIT = 120
_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_EXTENSIONS = {".txt", ".md", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


class Method(BaseModel):
    id: str
    title: str
    body: str = ""
    filename: str = ""
    size: int = 0
    created_at: str


class MethodsListResponse(BaseModel):
    methods: list[Method] = Field(default_factory=list)


def _store_path():
    return get_paths().base_dir / "methods.json"


def _read_methods() -> list[Method]:
    path = _store_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [Method.model_validate(item) for item in raw]


def _write_methods(methods: list[Method]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps([item.model_dump() for item in methods], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _clean_text(value: str, limit: int, field: str, *, allow_newlines: bool = False) -> str:
    text = value.strip()
    for char in text:
        if ord(char) < 32 and not (allow_newlines and char in "\n\t"):
            raise HTTPException(status_code=422, detail=f"{field} contains invalid characters.")
    if len(text) > limit:
        raise HTTPException(status_code=422, detail=f"{field} is too long.")
    return text


def _display_filename(raw_name: str, suffix: str) -> str:
    cleaned = "".join(char for char in Path(raw_name).name if char.isprintable() and char not in "\r\n\t")
    cleaned = cleaned.strip()[:_FILENAME_LIMIT]
    if not cleaned:
        cleaned = f"未命名{suffix}"
    if not cleaned.lower().endswith(suffix):
        cleaned = f"{cleaned[: _FILENAME_LIMIT - len(suffix)]}{suffix}"
    return cleaned


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _EXTENSIONS:
        raise HTTPException(status_code=422, detail="This file type is not supported.")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _FILE_BYTES:
            raise HTTPException(status_code=422, detail="File is too large.")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="File is empty.")
    return b"".join(chunks), suffix


async def _write_excerpt(path: Path) -> None:
    text = ""
    if path.suffix.lower() in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        markdown = await convert_file_to_markdown(path)
        if markdown is not None and markdown.is_file():
            text = markdown.read_text(encoding="utf-8", errors="replace")
            if markdown.resolve() != path.resolve():
                markdown.unlink(missing_ok=True)
    path.with_name(f"{path.stem}.excerpt.txt").write_text(text[:_EXCERPT_STORE_LIMIT], encoding="utf-8")


@router.get("/methods", response_model=MethodsListResponse)
async def list_methods() -> MethodsListResponse:
    try:
        return MethodsListResponse(methods=_read_methods())
    except Exception as exc:
        logger.error("Failed to list methods: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list methods") from exc


@router.post("/methods", response_model=Method, status_code=201)
async def create_method(
    title: str = Form(...),
    body: str = Form(""),
    file: UploadFile | None = File(None),
) -> Method:
    cleaned_title = _clean_text(title, _TITLE_LIMIT, "title")
    if not cleaned_title:
        raise HTTPException(status_code=422, detail="Title is required.")
    cleaned_body = _clean_text(body, _BODY_LIMIT, "body", allow_newlines=True) if body.strip() else ""
    payload: bytes | None = None
    suffix = ""
    filename = ""
    if file is not None and file.filename:
        payload, suffix = await _read_upload(file)
        filename = _display_filename(file.filename, suffix)
    method = Method(
        id=uuid.uuid4().hex[:12],
        title=cleaned_title,
        body=cleaned_body,
        filename=filename,
        size=len(payload or b""),
        created_at=datetime.now(UTC).isoformat(),
    )
    try:
        methods = _read_methods()
        if len(methods) >= _METHOD_LIMIT:
            raise HTTPException(status_code=422, detail="Too many methods.")
        if payload is not None:
            directory = get_paths().base_dir / "methods"
            directory.mkdir(parents=True, exist_ok=True)
            stored = directory / f"{method.id}{suffix}"
            stored.write_bytes(payload)
            await _write_excerpt(stored)
        updated = [method, *methods]
        _write_methods(updated)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create method: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create method") from exc
    return method


@router.get("/methods/{method_id}/file")
async def download_method_file(method_id: str) -> FileResponse:
    if not _ID_RE.fullmatch(method_id):
        raise HTTPException(status_code=404, detail="Method not found")
    method = next((item for item in _read_methods() if item.id == method_id), None)
    if method is None or not method.filename:
        raise HTTPException(status_code=404, detail="Method not found")
    path = get_paths().base_dir / "methods" / f"{method_id}{Path(method.filename).suffix.lower()}"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Method not found")
    return FileResponse(path, filename=method.filename)


@router.delete("/methods/{method_id}", status_code=204)
async def delete_method(method_id: str) -> None:
    if not _ID_RE.fullmatch(method_id):
        raise HTTPException(status_code=404, detail="Method not found")
    try:
        methods = _read_methods()
        current = next((item for item in methods if item.id == method_id), None)
        if current is None:
            raise HTTPException(status_code=404, detail="Method not found")
        directory = get_paths().base_dir / "methods"
        suffix = Path(current.filename).suffix.lower() if current.filename else ""
        for stored in (directory / f"{method_id}{suffix}", directory / f"{method_id}.excerpt.txt"):
            if stored.is_file():
                stored.unlink()
        _write_methods([item for item in methods if item.id != method_id])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete method: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete method") from exc
