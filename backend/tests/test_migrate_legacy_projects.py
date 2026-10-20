"""Tests for the legacy JSON → SQL project importer.

Covers the mapping the importer promises: project summary becomes the
consultation brief, materials become ``upload`` shelf documents with their
bytes, output records become ``output`` deliverables, listed conversations are
attached to the project, and a second run is a no-op.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio


def _legacy_payload(*, thread_ids: list[str] | None = None) -> list[dict]:
    return [
        {
            "id": "legacy-1",
            "name": "薪酬外部调查系统",
            "summary": "外部薪酬调查与对标",
            "materials": [
                {"id": "mat-1", "filename": "survey.md", "path": "materials/mat-1.md"},
            ],
            "outputs": [
                {"id": "out-1", "title": "调查结论", "note": "结论摘要"},
            ],
            "thread_ids": thread_ids or [],
        }
    ]


def _seed_legacy(root: Path, payload: list[dict] | None = None) -> Path:
    """Write the legacy ``projects.json`` plus the material files it references.

    A material whose dict carries ``"file": False`` is left without a file on
    disk — the layout a half-finished import leaves behind.
    """
    payload = payload if payload is not None else _legacy_payload()
    (root / "projects.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    for project in payload:
        materials = root / "projects" / str(project["id"]) / "materials"
        materials.mkdir(parents=True, exist_ok=True)
        for material in project.get("materials") or []:
            if material.get("file") is False:
                continue
            material_id = str(material["id"])
            (materials / f"{material_id}.md").write_text(f"# 原始材料 {material_id}\n", encoding="utf-8")
            (materials / f"{material_id}.excerpt.txt").write_text("摘录", encoding="utf-8")
    return root


@pytest.fixture
async def env(tmp_path):
    """A sqlite-backed store plus the repository handles the importer needs."""
    from deerflow.config.paths import Paths
    from deerflow.persistence.engine import close_engine, get_session_factory, init_engine
    from deerflow.persistence.projects import ProjectDocumentRepository, ProjectRepository
    from deerflow.persistence.thread_meta import ThreadMetaRepository

    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    await init_engine("sqlite", url=url, sqlite_dir=str(tmp_path))
    session_factory = get_session_factory()
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    yield {
        "projects": ProjectRepository(session_factory),
        "documents": ProjectDocumentRepository(session_factory),
        "threads": ThreadMetaRepository(session_factory),
        "paths": Paths(base_dir=legacy_root),
        "legacy_root": legacy_root,
    }
    await close_engine()


async def _import(env, *, user_id: str = "u1"):
    from scripts.migrate_legacy_projects import import_legacy_projects

    return await import_legacy_projects(
        project_repo=env["projects"],
        document_repo=env["documents"],
        thread_repo=env["threads"],
        paths=env["paths"],
        base_dir=env["legacy_root"],
        user_id=user_id,
    )


class TestImport:
    async def test_imports_project_documents_and_brief(self, env):
        _seed_legacy(env["legacy_root"])

        report = await _import(env)

        assert report.projects == 1
        assert report.documents == 2
        assert report.warnings == []

        projects = await env["projects"].list(user_id="u1")
        assert len(projects) == 1
        project = projects[0]
        assert project["name"] == "薪酬外部调查系统"
        # The legacy summary becomes upstream's consultation brief.
        assert project["instructions"] == "外部薪酬调查与对标"

        documents = await env["documents"].list_active(project["id"], limit=10, offset=0, user_id="u1")
        assert {doc["name"] for doc in documents} == {"survey.md", "调查结论"}
        kinds = {doc["name"]: doc["source_kind"] for doc in documents}
        assert kinds["survey.md"] == "upload"
        assert kinds["调查结论"] == "output"

    async def test_material_bytes_land_on_the_shelf(self, env):
        _seed_legacy(env["legacy_root"])

        await _import(env)

        project = (await env["projects"].list(user_id="u1"))[0]
        documents = await env["documents"].list_active(project["id"], limit=10, offset=0, user_id="u1")
        from deerflow.projects.documents import original_file_path

        material = next(doc for doc in documents if doc["name"] == "survey.md")
        shelf_file = original_file_path(env["paths"], user_id="u1", row=material)
        assert shelf_file.is_file()
        assert "原始材料 mat-1" in shelf_file.read_text(encoding="utf-8")

    async def test_output_record_becomes_a_markdown_deliverable(self, env):
        _seed_legacy(env["legacy_root"])

        await _import(env)

        project = (await env["projects"].list(user_id="u1"))[0]
        documents = await env["documents"].list_active(project["id"], limit=10, offset=0, user_id="u1")
        from deerflow.projects.documents import original_file_path

        output = next(doc for doc in documents if doc["name"] == "调查结论")
        body = original_file_path(env["paths"], user_id="u1", row=output).read_text(encoding="utf-8")
        assert "# 调查结论" in body
        assert "结论摘要" in body
        assert "长伴工作台旧版记录迁移而来" in body

    async def test_second_run_is_a_no_op(self, env):
        _seed_legacy(env["legacy_root"])

        first = await _import(env)
        second = await _import(env)

        assert first.projects == 1
        assert second.projects == 0
        assert second.documents == 0
        assert len(await env["projects"].list(user_id="u1")) == 1

    async def test_legacy_id_is_recorded_for_idempotency(self, env):
        _seed_legacy(env["legacy_root"])

        await _import(env)

        project = (await env["projects"].list(user_id="u1"))[0]
        assert project["presentation"]["legacy_id"] == "legacy-1"

    async def test_source_files_are_left_in_place(self, env):
        _seed_legacy(env["legacy_root"])
        legacy_file = env["legacy_root"] / "projects.json"

        await _import(env)

        assert legacy_file.is_file()
        assert (env["legacy_root"] / "projects" / "legacy-1" / "materials" / "mat-1.md").is_file()

    async def test_listed_thread_is_attached_to_the_project(self, env):
        _seed_legacy(env["legacy_root"], _legacy_payload(thread_ids=["thread-1"]))
        await env["threads"].create("thread-1", user_id="u1")

        report = await _import(env)

        assert report.threads == 1
        project = (await env["projects"].list(user_id="u1"))[0]
        thread = await env["threads"].get("thread-1", user_id="u1")
        assert thread["metadata"]["deerflow_project_id"] == project["id"]

    async def test_unknown_thread_is_reported_but_not_fatal(self, env):
        _seed_legacy(env["legacy_root"], _legacy_payload(thread_ids=["thread-missing"]))

        report = await _import(env)

        assert report.projects == 1
        assert report.threads == 0
        assert any("thread-missing" in warning for warning in report.warnings)

    async def test_material_without_a_file_is_skipped_with_a_warning(self, env):
        payload = _legacy_payload()
        payload[0]["materials"] = [{"id": "mat-missing", "filename": "gone.md", "file": False}]
        _seed_legacy(env["legacy_root"], payload)

        report = await _import(env)

        assert report.projects == 1
        # Only the output record survived; the material had no readable file.
        assert report.documents == 1
        assert any("gone.md" in warning for warning in report.warnings)

    async def test_other_users_cannot_see_the_imported_project(self, env):
        _seed_legacy(env["legacy_root"])

        await _import(env, user_id="u1")

        assert await env["projects"].list(user_id="u2") == []

    async def test_empty_legacy_layout_imports_nothing(self, env):
        report = await _import(env)

        assert (report.projects, report.documents, report.threads) == (0, 0, 0)
        assert report.warnings == []


class TestDryRun:
    async def test_dry_run_reports_without_writing(self, env, caplog):
        import logging

        _seed_legacy(env["legacy_root"])
        from scripts.migrate_legacy_projects import _report_dry_run

        with caplog.at_level(logging.INFO, logger="migrate_legacy_projects"):
            for legacy in json.loads((env["legacy_root"] / "projects.json").read_text(encoding="utf-8")):
                _report_dry_run(legacy)

        out = caplog.text
        assert "薪酬外部调查系统" in out
        assert "survey.md" in out
        assert "调查结论" in out
