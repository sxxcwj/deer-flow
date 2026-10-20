"""Local text search across projects, materials, and methods."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from deerflow.config.paths import get_paths

router = APIRouter(prefix="/api", tags=["search"])

_ID_RE = re.compile(r"^[a-f0-9]{12}$")
_RESULT_LIMIT = 20


class SearchHit(BaseModel):
    kind: str
    title: str
    snippet: str = ""
    project_id: str = ""
    target_id: str = ""


class SearchResponse(BaseModel):
    results: list[SearchHit] = Field(default_factory=list)


def _load_list(path: Path) -> list:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return raw if isinstance(raw, list) else []


def _snippet(text: str, needle: str) -> str:
    folded = text.casefold()
    index = folded.find(needle.casefold())
    if index < 0:
        return ""
    start = max(0, index - 24)
    end = min(len(text), index + len(needle) + 48)
    return text[start:end].replace("\n", " ").strip()


def _read_excerpt(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@router.get("/search", response_model=SearchResponse)
async def search_workbench(q: str = Query(..., min_length=1, max_length=80)) -> SearchResponse:
    needle = q.strip()
    if not needle or any(ord(char) < 32 for char in needle):
        raise HTTPException(status_code=422, detail="Query is invalid.")
    base = get_paths().base_dir
    hits: list[SearchHit] = []

    def add(hit: SearchHit) -> None:
        if len(hits) < _RESULT_LIMIT:
            hits.append(hit)

    for project in _load_list(base / "projects.json"):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        name = str(project.get("name") or "")
        summary = str(project.get("summary") or "")
        if _snippet(name, needle) or _snippet(summary, needle):
            add(SearchHit(kind="project", title=name, snippet=_snippet(f"{name} {summary}", needle), project_id=project_id, target_id=project_id))
        for output in project.get("outputs") or []:
            if not isinstance(output, dict):
                continue
            title = str(output.get("title") or "")
            note = str(output.get("note") or "")
            snippet = _snippet(f"{title} {note}", needle)
            if snippet:
                add(SearchHit(kind="output", title=title, snippet=snippet, project_id=project_id, target_id=str(output.get("id") or "")))
        if not _ID_RE.fullmatch(project_id):
            continue
        material_dir = base / "projects" / project_id / "materials"
        for material in project.get("materials") or []:
            if not isinstance(material, dict):
                continue
            material_id = str(material.get("id") or "")
            filename = str(material.get("filename") or "")
            excerpt = _read_excerpt(material_dir / f"{material_id}.excerpt.txt") if _ID_RE.fullmatch(material_id) else ""
            snippet = _snippet(filename, needle) or _snippet(excerpt, needle)
            if snippet:
                add(SearchHit(kind="material", title=filename or name, snippet=snippet, project_id=project_id, target_id=material_id))

    method_dir = base / "methods"
    for method in _load_list(base / "methods.json"):
        if not isinstance(method, dict):
            continue
        method_id = str(method.get("id") or "")
        title = str(method.get("title") or "")
        body = str(method.get("body") or "")
        excerpt = _read_excerpt(method_dir / f"{method_id}.excerpt.txt") if _ID_RE.fullmatch(method_id) else ""
        snippet = _snippet(f"{title} {body}", needle) or _snippet(excerpt, needle)
        if snippet:
            add(SearchHit(kind="method", title=title, snippet=snippet, target_id=method_id))

    return SearchResponse(results=hits)
