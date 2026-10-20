import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.project_context_middleware import ProjectContextMiddleware
from deerflow.config.paths import Paths
from deerflow.methods.brief import format_methods_brief


def _client(tmp_path):
    from app.gateway.routers import methods as methods_router
    from app.gateway.routers import projects as projects_router
    from app.gateway.routers import search as search_router

    app = FastAPI()
    app.include_router(methods_router.router)
    app.include_router(projects_router.router)
    app.include_router(search_router.router)
    paths = Paths(base_dir=tmp_path)
    patcher = patch.multiple(
        methods_router,
        get_paths=lambda: paths,
    )
    projects_patch = patch.object(projects_router, "get_paths", return_value=paths)
    search_patch = patch.object(search_router, "get_paths", return_value=paths)
    return patcher, projects_patch, search_patch, TestClient(app)


def test_create_text_method_and_inject_without_project(tmp_path):
    methods_patch, projects_patch, search_patch, client = _client(tmp_path)
    with methods_patch, projects_patch, search_patch, client:
        created = client.post("/api/methods", data={"title": "月薪口径", "body": "月薪按十三个月计算"})
        assert created.status_code == 201
        assert created.json()["title"] == "月薪口径"
        listed = client.get("/api/methods")
        assert listed.json()["methods"][0]["body"] == "月薪按十三个月计算"

    brief = format_methods_brief(tmp_path)
    assert "月薪按十三个月计算" in brief
    middleware = ProjectContextMiddleware(base_dir=str(tmp_path))
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
    assert "<project_context>" not in content


def test_reject_blank_method_title(tmp_path):
    methods_patch, projects_patch, search_patch, client = _client(tmp_path)
    with methods_patch, projects_patch, search_patch, client:
        response = client.post("/api/methods", data={"title": "   ", "body": ""})
    assert response.status_code == 422


def test_search_finds_material_excerpt(tmp_path):
    project_id = "abc123abc123"
    material_id = "a1b2c3d4e5f6"
    directory = tmp_path / "projects" / project_id / "materials"
    directory.mkdir(parents=True)
    (directory / f"{material_id}.excerpt.txt").write_text("只有材料里出现的口径词", encoding="utf-8")
    (tmp_path / "projects.json").write_text(
        json.dumps(
            [
                {
                    "id": project_id,
                    "name": "组织诊断",
                    "summary": "",
                    "materials": [{"id": material_id, "filename": "口径说明.txt"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    methods_patch, projects_patch, search_patch, client = _client(tmp_path)
    with methods_patch, projects_patch, search_patch, client:
        response = client.get("/api/search", params={"q": "只有材料里出现的口径词"})
    assert response.status_code == 200
    hits = response.json()["results"]
    assert hits[0]["kind"] == "material"
    assert hits[0]["project_id"] == project_id


def test_delete_method(tmp_path):
    methods_patch, projects_patch, search_patch, client = _client(tmp_path)
    with methods_patch, projects_patch, search_patch, client:
        created = client.post("/api/methods", data={"title": "月薪口径", "body": "一句"})
        method_id = created.json()["id"]
        deleted = client.delete(f"/api/methods/{method_id}")
        assert deleted.status_code == 204
        assert client.get("/api/methods").json()["methods"] == []
