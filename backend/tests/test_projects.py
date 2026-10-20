from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deerflow.config.paths import Paths


def _client(tmp_path):
    from app.gateway.routers import projects as projects_router

    app = FastAPI()
    app.include_router(projects_router.router)
    paths = Paths(base_dir=tmp_path)
    return patch.object(projects_router, "get_paths", return_value=paths), TestClient(app)


def test_project_list_starts_empty(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == {"projects": []}


def test_create_and_delete_project(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": " 组织诊断 ", "summary": "第一阶段"})
        assert created.status_code == 201
        body = created.json()
        assert body["name"] == "组织诊断"
        assert body["summary"] == "第一阶段"

        listed = client.get("/api/projects")
        assert listed.json()["projects"][0]["id"] == body["id"]

        deleted = client.delete(f"/api/projects/{body['id']}")
        assert deleted.status_code == 204
        assert client.get("/api/projects").json()["projects"] == []


def test_reject_blank_project_name(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        response = client.post("/api/projects", json={"name": "   "})
    assert response.status_code == 422


def test_delete_missing_project(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        response = client.delete("/api/projects/missing")
    assert response.status_code == 404


def test_legacy_project_has_no_threads(tmp_path):
    (tmp_path / "projects.json").write_text(
        '[{"id":"abc","name":"组织诊断","summary":"","updated_at":"2026-01-01T00:00:00+00:00"}]',
        encoding="utf-8",
    )
    patcher, client = _client(tmp_path)
    with patcher, client:
        response = client.get("/api/projects/abc")
    assert response.status_code == 200
    assert response.json()["thread_ids"] == []
    assert response.json()["materials"] == []


def test_attach_and_detach_thread(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        attached = client.put(
            f"/api/projects/{project_id}/threads",
            json={"thread_id": "fd66b189-4120-4558-911e-66d473ea7a3a"},
        )
        assert attached.status_code == 200
        assert attached.json()["thread_ids"] == ["fd66b189-4120-4558-911e-66d473ea7a3a"]

        again = client.put(
            f"/api/projects/{project_id}/threads",
            json={"thread_id": "fd66b189-4120-4558-911e-66d473ea7a3a"},
        )
        assert again.json()["thread_ids"] == ["fd66b189-4120-4558-911e-66d473ea7a3a"]

        detached = client.delete(
            f"/api/projects/{project_id}/threads/fd66b189-4120-4558-911e-66d473ea7a3a"
        )
        assert detached.status_code == 200
        assert detached.json()["thread_ids"] == []


def test_add_and_delete_output(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        added = client.post(
            f"/api/projects/{project_id}/outputs",
            json={"title": " 阶段记录 ", "note": "自己填写"},
        )
        assert added.status_code == 201
        body = added.json()
        assert body["outputs"][0]["title"] == "阶段记录"
        assert body["outputs"][0]["note"] == "自己填写"
        output_id = body["outputs"][0]["id"]

        deleted = client.delete(f"/api/projects/{project_id}/outputs/{output_id}")
        assert deleted.status_code == 200
        assert deleted.json()["outputs"] == []


def test_reject_blank_output_title(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        response = client.post(
            f"/api/projects/{created.json()['id']}/outputs",
            json={"title": "  "},
        )
    assert response.status_code == 422


def test_reject_invalid_thread_id(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        response = client.put(
            f"/api/projects/{project_id}/threads",
            json={"thread_id": "../secrets"},
        )
    assert response.status_code == 422


def test_upload_and_delete_material(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        uploaded = client.post(
            f"/api/projects/{project_id}/materials",
            files={"file": ("../../口径说明.txt", "月薪按十三个月计算".encode(), "text/plain")},
        )
        assert uploaded.status_code == 201
        material = uploaded.json()["materials"][0]
        assert material["filename"] == "口径说明.txt"
        assert ".." not in material["filename"]
        stored = list((tmp_path / "projects" / project_id / "materials").glob(f"{material['id']}*"))
        assert stored
        assert all(path.parent == tmp_path / "projects" / project_id / "materials" for path in stored)

        downloaded = client.get(f"/api/projects/{project_id}/materials/{material['id']}")
        assert downloaded.status_code == 200
        assert "月薪按十三个月计算" in downloaded.text

        deleted = client.delete(f"/api/projects/{project_id}/materials/{material['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["materials"] == []
        assert client.get(f"/api/projects/{project_id}/materials/{material['id']}").status_code == 404


def test_reject_unsupported_or_empty_material(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        rejected = client.post(
            f"/api/projects/{project_id}/materials",
            files={"file": ("notes.exe", b"hello", "application/octet-stream")},
        )
        empty = client.post(
            f"/api/projects/{project_id}/materials",
            files={"file": ("notes.txt", b"", "text/plain")},
        )
    assert rejected.status_code == 422
    assert empty.status_code == 422


def test_reject_oversized_material(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        response = client.post(
            f"/api/projects/{project_id}/materials",
            files={"file": ("notes.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        )
    assert response.status_code == 422


def test_reject_too_many_materials(tmp_path):
    created = {
        "id": "abc123abc123",
        "name": "组织诊断",
        "summary": "",
        "thread_ids": [],
        "outputs": [],
        "materials": [
            {"id": f"{index:012x}", "filename": f"{index}.txt", "size": 1, "created_at": "2026-01-01T00:00:00+00:00"}
            for index in range(20)
        ],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    (tmp_path / "projects.json").write_text(f"[{__import__('json').dumps(created)}]", encoding="utf-8")
    patcher, client = _client(tmp_path)
    with patcher, client:
        response = client.post(
            "/api/projects/abc123abc123/materials",
            files={"file": ("extra.txt", b"more", "text/plain")},
        )
    assert response.status_code == 422


def test_save_attached_chat_file_as_material(tmp_path):
    patcher, client = _client(tmp_path)
    thread_id = "fd66b189-4120-4558-911e-66d473ea7a3a"
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        client.put(f"/api/projects/{project_id}/threads", json={"thread_id": thread_id})
        outputs = Paths(base_dir=tmp_path).sandbox_outputs_dir(thread_id)
        outputs.mkdir(parents=True)
        (outputs / "口径.txt").write_text("月薪按十三个月计算", encoding="utf-8")
        saved = client.post(
            f"/api/projects/{project_id}/materials/from-chat",
            json={"thread_id": thread_id, "path": "/mnt/user-data/outputs/口径.txt"},
        )
        assert saved.status_code == 201
        assert saved.json()["materials"][0]["filename"] == "口径.txt"
        rejected = client.post(
            f"/api/projects/{project_id}/materials/from-chat",
            json={"thread_id": thread_id, "path": "/mnt/user-data/outputs/../../secrets.txt"},
        )
        assert rejected.status_code == 422
        unattached = client.post(
            "/api/projects",
            json={"name": "另一个"},
        )
        other_id = unattached.json()["id"]
        denied = client.post(
            f"/api/projects/{other_id}/materials/from-chat",
            json={"thread_id": thread_id, "path": "/mnt/user-data/outputs/口径.txt"},
        )
        assert denied.status_code == 422


def test_delete_project_removes_material_files(tmp_path):
    patcher, client = _client(tmp_path)
    with patcher, client:
        created = client.post("/api/projects", json={"name": "组织诊断"})
        project_id = created.json()["id"]
        client.post(
            f"/api/projects/{project_id}/materials",
            files={"file": ("口径.txt", "一句".encode(), "text/plain")},
        )
        deleted = client.delete(f"/api/projects/{project_id}")
        assert deleted.status_code == 204
    assert not (tmp_path / "projects" / project_id).exists()
