"""Local project list for the workbench. Names are entered by the user."""

import json
import logging
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from deerflow.config.paths import get_paths
from deerflow.utils.file_conversion import convert_file_to_markdown

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["projects"])

_NAME_LIMIT = 80
_SUMMARY_LIMIT = 500
_OUTPUT_LIMIT = 50
_MATERIAL_LIMIT = 20
_MATERIAL_BYTES = 10 * 1024 * 1024
_EXCERPT_STORE_LIMIT = 20_000
_FILENAME_LIMIT = 120
_PROJECT_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_MATERIAL_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}


class ProjectOutput(BaseModel):
    id: str
    title: str
    note: str = ""
    created_at: str


class ProjectMaterial(BaseModel):
    id: str
    filename: str
    size: int
    created_at: str


class Project(BaseModel):
    id: str
    name: str
    summary: str = ""
    thread_ids: list[str] = Field(default_factory=list)
    outputs: list[ProjectOutput] = Field(default_factory=list)
    materials: list[ProjectMaterial] = Field(default_factory=list)
    updated_at: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Project name entered by the user")
    summary: str = Field(default="", description="Short note")


class ProjectThreadRequest(BaseModel):
    thread_id: str = Field(..., description="Existing conversation id")


class ProjectOutputRequest(BaseModel):
    title: str = Field(..., description="Title entered by the user")
    note: str = Field(default="", description="Short note")


class ProjectMaterialFromChatRequest(BaseModel):
    thread_id: str
    path: str


class ProjectsListResponse(BaseModel):
    projects: list[Project]


def _store_path():
    return get_paths().base_dir / "projects.json"


def _read_projects() -> list[Project]:
    path = _store_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [Project.model_validate(item) for item in raw]


def _write_projects(projects: list[Project]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump() for item in projects]
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _clean_text(value: str, limit: int, field: str) -> str:
    text = value.strip()
    if any(ord(char) < 32 for char in text):
        raise HTTPException(status_code=422, detail=f"{field} contains invalid characters.")
    if len(text) > limit:
        raise HTTPException(status_code=422, detail=f"{field} is too long.")
    return text


def _clean_thread_id(value: str) -> str:
    text = value.strip()
    if (
        not text
        or len(text) > 80
        or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in text)
    ):
        raise HTTPException(status_code=422, detail="thread_id is invalid.")
    return text


def _materials_dir(project_id: str) -> Path:
    if not _PROJECT_ID_RE.fullmatch(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return get_paths().base_dir / "projects" / project_id / "materials"


def _display_filename(raw_name: str, suffix: str) -> str:
    base = Path(raw_name).name
    cleaned = "".join(char for char in base if char.isprintable() and char not in "\r\n\t")
    cleaned = cleaned.strip()[:_FILENAME_LIMIT]
    if not cleaned:
        cleaned = f"未命名{suffix}"
    if not cleaned.lower().endswith(suffix):
        cleaned = f"{cleaned[: _FILENAME_LIMIT - len(suffix)]}{suffix}"
    return cleaned


async def _persist_material(project_id: str, display_name: str, suffix: str, data: bytes) -> Project:
    if suffix not in _MATERIAL_EXTENSIONS:
        raise HTTPException(status_code=422, detail="This file type is not supported.")
    if not data:
        raise HTTPException(status_code=422, detail="File is empty.")
    if len(data) > _MATERIAL_BYTES:
        raise HTTPException(status_code=422, detail="File is too large.")
    material = ProjectMaterial(
        id=uuid.uuid4().hex[:12],
        filename=display_name,
        size=len(data),
        created_at=datetime.now(UTC).isoformat(),
    )
    projects = _read_projects()
    current = _find_project(projects, project_id)
    if len(current.materials) >= _MATERIAL_LIMIT:
        raise HTTPException(status_code=422, detail="Too many materials on this project.")
    directory = _materials_dir(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    stored = directory / f"{material.id}{suffix}"
    stored.write_bytes(data)
    await _write_excerpt(stored)
    updated = current.model_copy(
        update={
            "materials": [material, *current.materials],
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    _write_projects([updated if item.id == project_id else item for item in projects])
    return updated


async def _write_excerpt(path: Path) -> None:
    text = ""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        markdown = await convert_file_to_markdown(path)
        if markdown is not None and markdown.is_file():
            text = markdown.read_text(encoding="utf-8", errors="replace")
            if markdown.resolve() != path.resolve():
                markdown.unlink(missing_ok=True)
    path.with_name(f"{path.stem}.excerpt.txt").write_text(
        text[:_EXCERPT_STORE_LIMIT],
        encoding="utf-8",
    )


def _find_project(projects: list[Project], project_id: str) -> Project:
    for item in projects:
        if item.id == project_id:
            return item
    raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects", response_model=ProjectsListResponse)
async def list_projects() -> ProjectsListResponse:
    try:
        return ProjectsListResponse(projects=_read_projects())
    except Exception as exc:
        logger.error("Failed to list projects: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list projects") from exc


@router.post("/projects", response_model=Project, status_code=201)
async def create_project(request: ProjectCreateRequest) -> Project:
    name = _clean_text(request.name, _NAME_LIMIT, "name")
    if not name:
        raise HTTPException(status_code=422, detail="Project name is required.")
    summary = _clean_text(request.summary, _SUMMARY_LIMIT, "summary")
    project = Project(
        id=uuid.uuid4().hex[:12],
        name=name,
        summary=summary,
        updated_at=datetime.now(UTC).isoformat(),
    )
    try:
        projects = _read_projects()
        projects.insert(0, project)
        _write_projects(projects)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create project: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create project") from exc
    return project


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    try:
        return _find_project(_read_projects(), project_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to read project: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read project") from exc


@router.put("/projects/{project_id}/threads", response_model=Project)
async def attach_project_thread(project_id: str, request: ProjectThreadRequest) -> Project:
    thread_id = _clean_thread_id(request.thread_id)
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        thread_ids = [thread_id, *[item for item in current.thread_ids if item != thread_id]]
        if len(thread_ids) > 50:
            raise HTTPException(status_code=422, detail="Too many conversations on this project.")
        updated = current.model_copy(
            update={
                "thread_ids": thread_ids,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_projects([updated if item.id == project_id else item for item in projects])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to attach conversation: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to attach conversation") from exc
    return updated


@router.delete("/projects/{project_id}/threads/{thread_id}", response_model=Project)
async def detach_project_thread(project_id: str, thread_id: str) -> Project:
    thread_id = _clean_thread_id(thread_id)
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        updated = current.model_copy(
            update={
                "thread_ids": [item for item in current.thread_ids if item != thread_id],
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_projects([updated if item.id == project_id else item for item in projects])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to detach conversation: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to detach conversation") from exc
    return updated


@router.post("/projects/{project_id}/outputs", response_model=Project, status_code=201)
async def add_project_output(project_id: str, request: ProjectOutputRequest) -> Project:
    title = _clean_text(request.title, _NAME_LIMIT, "title")
    if not title:
        raise HTTPException(status_code=422, detail="Output title is required.")
    note = _clean_text(request.note, _SUMMARY_LIMIT, "note")
    output = ProjectOutput(
        id=uuid.uuid4().hex[:12],
        title=title,
        note=note,
        created_at=datetime.now(UTC).isoformat(),
    )
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        outputs = [output, *current.outputs]
        if len(outputs) > _OUTPUT_LIMIT:
            raise HTTPException(status_code=422, detail="Too many outputs on this project.")
        updated = current.model_copy(
            update={
                "outputs": outputs,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_projects([updated if item.id == project_id else item for item in projects])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to add output: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add output") from exc
    return updated


@router.delete("/projects/{project_id}/outputs/{output_id}", response_model=Project)
async def delete_project_output(project_id: str, output_id: str) -> Project:
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        outputs = [item for item in current.outputs if item.id != output_id]
        if len(outputs) == len(current.outputs):
            raise HTTPException(status_code=404, detail="Output not found")
        updated = current.model_copy(
            update={
                "outputs": outputs,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_projects([updated if item.id == project_id else item for item in projects])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete output: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete output") from exc
    return updated


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str) -> None:
    try:
        projects = _read_projects()
        remaining = [item for item in projects if item.id != project_id]
        if len(remaining) == len(projects):
            raise HTTPException(status_code=404, detail="Project not found")
        _write_projects(remaining)
        if _PROJECT_ID_RE.fullmatch(project_id):
            project_dir = get_paths().base_dir / "projects" / project_id
            if project_dir.is_dir():
                shutil.rmtree(project_dir)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete project: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete project") from exc


@router.post("/projects/{project_id}/materials", response_model=Project, status_code=201)
async def add_project_material(project_id: str, file: UploadFile = File(...)) -> Project:
    raw_name = file.filename or ""
    suffix = Path(raw_name).suffix.lower()
    if suffix not in _MATERIAL_EXTENSIONS:
        raise HTTPException(status_code=422, detail="This file type is not supported.")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MATERIAL_BYTES:
            raise HTTPException(status_code=422, detail="File is too large.")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="File is empty.")
    display_name = _display_filename(raw_name, suffix)
    try:
        return await _persist_material(project_id, display_name, suffix, b"".join(chunks))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to add material: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add material") from exc


@router.post("/projects/{project_id}/materials/from-chat", response_model=Project, status_code=201)
async def save_chat_file_as_material(project_id: str, request: ProjectMaterialFromChatRequest) -> Project:
    thread_id = _clean_thread_id(request.thread_id)
    virtual_path = request.path.strip()
    if not virtual_path.startswith("/"):
        virtual_path = f"/{virtual_path}"
    if not virtual_path.startswith("/mnt/user-data/") or ".." in virtual_path:
        raise HTTPException(status_code=422, detail="File path is invalid.")
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        if thread_id not in current.thread_ids:
            raise HTTPException(status_code=422, detail="Conversation is not attached to this project.")
        actual = get_paths().resolve_virtual_path(thread_id, virtual_path)
        if not actual.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        data = actual.read_bytes()
        suffix = actual.suffix.lower()
        return await _persist_material(project_id, _display_filename(actual.name, suffix), suffix, data)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="File path is invalid.") from exc
    except Exception as exc:
        logger.error("Failed to save chat file as material: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save material") from exc


@router.get("/projects/{project_id}/materials/{material_id}")
async def download_project_material(project_id: str, material_id: str) -> FileResponse:
    if not _PROJECT_ID_RE.fullmatch(material_id):
        raise HTTPException(status_code=404, detail="Material not found")
    projects = _read_projects()
    current = _find_project(projects, project_id)
    material = next((item for item in current.materials if item.id == material_id), None)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    suffix = Path(material.filename).suffix.lower()
    path = _materials_dir(project_id) / f"{material_id}{suffix}"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Material not found")
    return FileResponse(path, filename=material.filename)


@router.delete("/projects/{project_id}/materials/{material_id}", response_model=Project)
async def delete_project_material(project_id: str, material_id: str) -> Project:
    if not _PROJECT_ID_RE.fullmatch(material_id):
        raise HTTPException(status_code=404, detail="Material not found")
    try:
        projects = _read_projects()
        current = _find_project(projects, project_id)
        material = next((item for item in current.materials if item.id == material_id), None)
        if material is None:
            raise HTTPException(status_code=404, detail="Material not found")
        directory = _materials_dir(project_id)
        suffix = Path(material.filename).suffix.lower()
        for stored in (directory / f"{material_id}{suffix}", directory / f"{material_id}.excerpt.txt"):
            if stored.is_file():
                stored.unlink()
        updated = current.model_copy(
            update={
                "materials": [item for item in current.materials if item.id != material_id],
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        _write_projects([updated if item.id == project_id else item for item in projects])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete material: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete material") from exc
    return updated
