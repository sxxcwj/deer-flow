"""Workbench search across projects, project documents, and firm methods.

Projects and their documents live in upstream's SQL-backed store (owner-scoped,
see ``app/gateway/routers/projects.py``); firm methods are 长伴's own file-backed
catalogue (``methods.json``). Both are searched here so the workbench home has
one entry point.
"""

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.gateway.authz import require_permission
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

_RESULT_LIMIT = 20
_PROJECT_SCAN_LIMIT = 100
_DOCUMENT_SCAN_LIMIT = 50
_ID_RE = re.compile(r"^[a-f0-9]{12}$")


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


def _project_repo(request: Request):
    """Return upstream's project repository, or None when it is unavailable.

    The repository is only mounted when the Gateway runs with a database
    configured. A local-only deployment still has the methods catalogue, so
    search degrades to that instead of failing the whole request.
    """
    return getattr(request.app.state, "project_repo", None)


def _document_repo(request: Request):
    return getattr(request.app.state, "project_document_repo", None)


@router.get("/search", response_model=SearchResponse)
@require_permission("projects", "read")
async def search_workbench(request: Request, q: str = Query(..., min_length=1, max_length=80)) -> SearchResponse:
    needle = q.strip()
    if not needle or any(ord(char) < 32 for char in needle):
        raise HTTPException(status_code=422, detail="Query is invalid.")

    hits: list[SearchHit] = []

    def add(hit: SearchHit) -> None:
        if len(hits) < _RESULT_LIMIT:
            hits.append(hit)

    # 1) Upstream projects and their shelf documents.
    project_repo = _project_repo(request)
    document_repo = _document_repo(request)
    if project_repo is not None:
        try:
            projects = await project_repo.list()
        except Exception:
            logger.warning("Could not list projects for search", exc_info=True)
            projects = []
        for project in projects[:_PROJECT_SCAN_LIMIT]:
            if not isinstance(project, dict):
                continue
            project_id = str(project.get("id") or "")
            name = str(project.get("name") or "")
            instructions = str(project.get("instructions") or "")
            if _snippet(name, needle) or _snippet(instructions, needle):
                add(
                    SearchHit(
                        kind="project",
                        title=name,
                        snippet=_snippet(f"{name} {instructions}", needle),
                        project_id=project_id,
                        target_id=project_id,
                    )
                )
            if document_repo is None or not project_id:
                continue
            try:
                documents = await document_repo.list_active(project_id, limit=_DOCUMENT_SCAN_LIMIT, offset=0)
            except Exception:
                logger.debug("Could not list documents for project %s", project_id, exc_info=True)
                continue
            for document in documents:
                if not isinstance(document, dict):
                    continue
                title = str(document.get("name") or "")
                summary = str(document.get("summary") or "")
                snippet = _snippet(f"{title} {summary}", needle)
                if not snippet:
                    continue
                # ``upload`` is a material the user brought in; ``output`` is a
                # deliverable promoted from a thread's artifacts.
                kind = "material" if document.get("source_kind") == "upload" else "output"
                add(
                    SearchHit(
                        kind=kind,
                        title=title or name,
                        snippet=snippet,
                        project_id=project_id,
                        target_id=str(document.get("id") or ""),
                    )
                )

    # 2) 长伴 firm methods (file-backed catalogue).
    base = get_paths().base_dir
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
