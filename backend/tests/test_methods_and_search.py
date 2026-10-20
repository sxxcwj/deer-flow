import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from starlette.middleware.base import BaseHTTPMiddleware

from app.gateway.authz import AuthContext, Permissions
from deerflow.agents.middlewares.methods_context_middleware import MethodsContextMiddleware
from deerflow.config.paths import Paths
from deerflow.methods.brief import format_methods_brief
from deerflow.runtime.user_context import reset_current_user, set_current_user

_STUB_PERMISSIONS: list[str] = [
    Permissions.THREADS_READ,
    Permissions.MEMORY_READ,
    Permissions.AGENTS_READ,
    Permissions.PROJECTS_READ,
]


class _StubAuthMiddleware(BaseHTTPMiddleware):
    """Stamp a permissive AuthContext so ``@require_permission`` passes.

    Mirrors upstream's ``tests/test_projects_router.py``: search reads
    owner-scoped project data, so it needs ``projects:read`` granted.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        user = SimpleNamespace(id="user-a", system_role="user")
        request.state.user = user
        request.state.auth = AuthContext(user=user, permissions=list(_STUB_PERMISSIONS))
        token = set_current_user(user)
        try:
            return await call_next(request)
        finally:
            reset_current_user(token)


def _client(tmp_path, *, projects=None, documents=None):
    from app.gateway.routers import methods as methods_router
    from app.gateway.routers import search as search_router

    # Only the 长伴-owned routers are mounted here. The projects router is
    # upstream's (SQL-backed) and is covered by upstream's own tests; search
    # reads upstream's project repository directly, so it is stubbed here.
    app = FastAPI()
    app.add_middleware(_StubAuthMiddleware)
    app.include_router(methods_router.router)
    app.include_router(search_router.router)
    app.state.project_repo = projects
    app.state.project_document_repo = documents
    paths = Paths(base_dir=tmp_path)
    patcher = patch.multiple(
        methods_router,
        get_paths=lambda: paths,
    )
    search_patch = patch.object(search_router, "get_paths", return_value=paths)
    return patcher, search_patch, TestClient(app)


def test_create_text_method_and_inject_without_project(tmp_path):
    methods_patch, search_patch, client = _client(tmp_path)
    with methods_patch, search_patch, client:
        created = client.post("/api/methods", data={"title": "月薪口径", "body": "月薪按十三个月计算"})
        assert created.status_code == 201
        assert created.json()["title"] == "月薪口径"
        listed = client.get("/api/methods")
        assert listed.json()["methods"][0]["body"] == "月薪按十三个月计算"

    brief = format_methods_brief(tmp_path)
    assert "月薪按十三个月计算" in brief
    middleware = MethodsContextMiddleware(base_dir=str(tmp_path))
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="这次没有项目材料")],
        runtime=cast(Runtime, SimpleNamespace(context={})),
    )
    sent = {}

    def handler(req):
        sent["request"] = req
        return "ok"

    middleware.wrap_model_call(request, handler)
    content = sent["request"].messages[-1].content
    assert "月薪按十三个月计算" in content
    assert "<method_context>" in content


def test_reject_blank_method_title(tmp_path):
    methods_patch, search_patch, client = _client(tmp_path)
    with methods_patch, search_patch, client:
        response = client.post("/api/methods", data={"title": "   ", "body": ""})
    assert response.status_code == 422


class _StubProjectRepo:
    def __init__(self, rows):
        self._rows = rows

    async def list(self, status=None, user_id=None):
        return list(self._rows)


class _StubDocumentRepo:
    def __init__(self, rows_by_project):
        self._rows = rows_by_project

    async def list_active(self, project_id, *, limit, offset, user_id=None):
        return list(self._rows.get(project_id, []))[:limit]


def test_search_finds_project_document(tmp_path):
    project_id = "abc123abc123"
    material_id = "a1b2c3d4e5f6"
    projects = _StubProjectRepo([{"id": project_id, "name": "组织诊断", "instructions": "第一阶段"}])
    documents = _StubDocumentRepo(
        {
            project_id: [
                {
                    "id": material_id,
                    "name": "口径说明.txt",
                    "summary": "只有材料里出现的口径词",
                    "source_kind": "upload",
                }
            ]
        }
    )
    methods_patch, search_patch, client = _client(tmp_path, projects=projects, documents=documents)
    with methods_patch, search_patch, client:
        response = client.get("/api/search", params={"q": "只有材料里出现的口径词"})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert hits[0]["kind"] == "material"
    assert hits[0]["project_id"] == project_id


def test_search_finds_project_deliverable(tmp_path):
    project_id = "abc123abc123"
    projects = _StubProjectRepo([{"id": project_id, "name": "组织诊断", "instructions": ""}])
    documents = _StubDocumentRepo(
        {
            project_id: [
                {
                    "id": "d0d0d0d0d0d0",
                    "name": "阶段报告.md",
                    "summary": "交付物里出现的结论",
                    "source_kind": "output",
                }
            ]
        }
    )
    methods_patch, search_patch, client = _client(tmp_path, projects=projects, documents=documents)
    with methods_patch, search_patch, client:
        response = client.get("/api/search", params={"q": "交付物里出现的结论"})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert hits[0]["kind"] == "output"
    assert hits[0]["project_id"] == project_id


def test_search_finds_project_by_instructions(tmp_path):
    project_id = "abc123abc123"
    projects = _StubProjectRepo([{"id": project_id, "name": "组织诊断", "instructions": "薪酬口径按十三个月"}])
    methods_patch, search_patch, client = _client(tmp_path, projects=projects)
    with methods_patch, search_patch, client:
        response = client.get("/api/search", params={"q": "薪酬口径"})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert hits[0]["kind"] == "project"
    assert hits[0]["target_id"] == project_id


def test_search_degrades_when_project_store_unavailable(tmp_path):
    """A deployment without a database still searches the methods catalogue."""
    method_id = "a1b2c3d4e5f6"
    (tmp_path / "methods.json").write_text(
        json.dumps([{"id": method_id, "title": "月薪口径", "body": "月薪按十三个月计算"}]),
        encoding="utf-8",
    )
    methods_patch, search_patch, client = _client(tmp_path)
    with methods_patch, search_patch, client:
        response = client.get("/api/search", params={"q": "十三个月"})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert hits[0]["kind"] == "method"


def test_delete_method(tmp_path):
    methods_patch, search_patch, client = _client(tmp_path)
    with methods_patch, search_patch, client:
        created = client.post("/api/methods", data={"title": "月薪口径", "body": "一句"})
        method_id = created.json()["id"]
        deleted = client.delete(f"/api/methods/{method_id}")
        assert deleted.status_code == 204
        assert client.get("/api/methods").json()["methods"] == []
