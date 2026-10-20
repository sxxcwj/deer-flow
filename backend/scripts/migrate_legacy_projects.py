#!/usr/bin/env python
"""One-shot importer: copy the legacy JSON-backed workbench projects into
upstream's SQL project store.

The 长伴 workbench used to keep projects in ``{base_dir}/projects.json`` with
material files under ``{base_dir}/projects/{project_id}/materials/``. Upstream
replaced that with an owner-scoped SQL store (projects + a document shelf).
This importer bridges the two so a workbench carried over from the old layout
survives the upstream sync.

Mapping:
- project name    -> ``projects.name``
- project summary -> ``projects.instructions`` (upstream's consultation brief)
- material file   -> a shelf document with ``source_kind == "upload"``; the
  original bytes are staged so upstream derives the markdown itself
- output record   -> a shelf document with ``source_kind == "output"`` whose
  body is the recorded title and note (the legacy layout stored no bytes)
- thread_ids      -> ``threads_meta.project_id`` for each listed conversation

Design (mirrors ``scripts/migrate_agents_to_db.py``):
- Explicit, operator-run. Nothing auto-imports on boot.
- Idempotent: the legacy id is recorded in ``presentation.legacy_id`` and an
  already-imported project is skipped, so re-running is safe.
- Non-destructive: the legacy JSON and material files are left in place.

Usage (from the ``backend/`` directory — the Gateway's own working
directory, which is what ``database.sqlite_dir`` is relative to)::

    uv run python scripts/migrate_legacy_projects.py [--dry-run] [--user-id ID]

Requires ``database.backend`` to be ``sqlite`` or ``postgres`` in config.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from deerflow.config.app_config import get_app_config
from deerflow.config.paths import Paths, get_paths
from deerflow.persistence.engine import get_session_factory, init_engine_from_config
from deerflow.persistence.projects.sql import ProjectDocumentRepository, ProjectRepository
from deerflow.persistence.thread_meta import THREAD_PROJECT_METADATA_KEY
from deerflow.persistence.thread_meta.sql import ThreadMetaRepository
from deerflow.projects.documents import (
    add_staged_document,
    stage_document_bytes,
    validate_shelf_filename,
)
from deerflow.runtime.user_context import get_effective_user_id

logger = logging.getLogger("migrate_legacy_projects")

#: Answers "does this thread still have recoverable conversation content?".
ThreadRecovery = Callable[[str], Awaitable[bool]]

_LEGACY_PRESENTATION_KEY = "legacy_id"
_DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024


@dataclass
class LegacyImportReport:
    """What one import pass did, for the operator log and the tests."""

    projects: int = 0
    documents: int = 0
    threads: int = 0
    warnings: list[str] = field(default_factory=list)


def _legacy_projects(base_dir: Path) -> list[dict]:
    path = base_dir / "projects.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read %s", path)
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _material_dir(base_dir: Path, project_id: str) -> Path:
    return base_dir / "projects" / project_id / "materials"


def _material_source(base_dir: Path, project_id: str, material_id: str) -> Path | None:
    """The original material file (not the derived excerpt)."""
    directory = _material_dir(base_dir, project_id)
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.iterdir()):
        if candidate.stem == material_id and candidate.suffix != ".txt":
            return candidate
    return None


def _output_body(title: str, note: str) -> bytes:
    """Render a legacy output record as a markdown deliverable body."""
    lines = [f"# {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.append("_由长伴工作台旧版记录迁移而来。_")
    return "\n".join(lines).encode("utf-8")


async def _thread_has_checkpoint(thread_id: str) -> bool:
    """Does the checkpointer still hold a checkpoint for this thread?

    The old workbench kept its conversations in the LangGraph checkpointer
    only. Upstream added a ``threads_meta`` table on top of it, so a thread
    whose metadata row is gone is invisible in the UI even though its messages
    are still on disk. This is the probe that tells the importer the
    conversation is recoverable.
    """
    from deerflow.runtime.checkpointer import make_checkpointer

    try:
        async with make_checkpointer() as checkpointer:
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            checkpoint_tuple = await checkpointer.aget_tuple(config)
            return checkpoint_tuple is not None
    except Exception as exc:  # noqa: BLE001 — a missing checkpointer is not fatal
        logger.warning("Could not probe the checkpointer for thread %s: %s", thread_id, exc)
        return False


def _report_dry_run(legacy: dict) -> None:
    """Describe what a legacy project would contribute, without touching the db."""
    name = str(legacy.get("name") or "").strip()
    logger.info("[dry-run] would import project %r (legacy id %s)", name, legacy.get("id"))
    for material in legacy.get("materials") or []:
        if isinstance(material, dict):
            logger.info("[dry-run]   material %r", material.get("filename"))
    for output in legacy.get("outputs") or []:
        if isinstance(output, dict):
            logger.info("[dry-run]   output %r", output.get("title"))
    for thread_id in legacy.get("thread_ids") or []:
        logger.info("[dry-run]   attach thread %s", thread_id)


async def _attach_threads(
    *,
    thread_repo: ThreadMetaRepository,
    legacy: dict,
    project_id: str,
    project_name: str,
    user_id: str,
    recover_thread: ThreadRecovery | None,
) -> tuple[int, list[str]]:
    """Attach the legacy project's conversations to it. Returns (attached, warnings)."""
    warnings: list[str] = []
    attached = 0
    for thread_id in legacy.get("thread_ids") or []:
        if not isinstance(thread_id, str) or not thread_id:
            continue
        current = await thread_repo.get(thread_id, user_id=user_id)
        current_project = None
        if current is not None:
            metadata = current.get("metadata") or {}
            current_project = metadata.get(THREAD_PROJECT_METADATA_KEY) if isinstance(metadata, dict) else None
        if current_project is not None and current_project != project_id:
            # Upstream's model gives a conversation exactly one project, and
            # ``set_project`` overwrites rather than refuses. The old workbench
            # let several projects point at the same conversation, so the first
            # project to claim it keeps it and the others are reported.
            warnings.append(f"project {project_name!r}: thread {thread_id} already belongs to another project and was left there")
            continue
        bound = await thread_repo.set_project(thread_id, project_id, user_id=user_id)
        if not bound and recover_thread is not None and await recover_thread(thread_id):
            # The conversation survived in the checkpointer but lost its
            # metadata row when the old workbench layout was retired. Upstream
            # creates that row on demand (see the goal path in
            # ``app/gateway/routers/threads.py``); recreate it so the thread
            # shows up in the list again, then attach the project.
            try:
                await thread_repo.create(thread_id, user_id=user_id)
            except Exception as exc:  # noqa: BLE001 — never abort the batch
                warnings.append(f"project {project_name!r}: thread {thread_id} could not be recovered ({exc})")
                continue
            bound = await thread_repo.set_project(thread_id, project_id, user_id=user_id)
        if bound:
            attached += 1
            logger.info("  thread %s now belongs to project %s", thread_id, project_id)
        else:
            warnings.append(f"project {project_name!r}: thread {thread_id} was not attached (no such thread row, or it already belongs to another project)")
    return attached, warnings


async def _import_project(
    *,
    project_repo: ProjectRepository,
    document_repo: ProjectDocumentRepository,
    thread_repo: ThreadMetaRepository,
    paths: Paths,
    base_dir: Path,
    legacy: dict,
    user_id: str,
    max_file_size: int,
    recover_thread: ThreadRecovery | None = None,
) -> tuple[int, int, int, list[str]]:
    """Import one legacy project. Returns (projects, documents, threads, warnings)."""
    warnings: list[str] = []
    legacy_id = str(legacy.get("id") or "")
    name = str(legacy.get("name") or "").strip()
    if not legacy_id or not name:
        warnings.append(f"skipping a record with no id/name: {legacy!r}")
        return 0, 0, 0, warnings

    # Idempotency: the legacy id is recorded in ``presentation`` so a second
    # run recognises its own earlier import. The documents are not touched
    # again, but the conversations are still (re)attached: a thread that lost
    # its metadata row can be recovered long after the project itself was
    # imported.
    for existing in await project_repo.list(user_id=user_id):
        presentation = existing.get("presentation") or {}
        if isinstance(presentation, dict) and presentation.get(_LEGACY_PRESENTATION_KEY) == legacy_id:
            logger.info("skip project %r: already imported as %s", name, existing.get("id"))
            project_id = str(existing.get("id"))
            threads, thread_warnings = await _attach_threads(
                thread_repo=thread_repo,
                legacy=legacy,
                project_id=project_id,
                project_name=name,
                user_id=user_id,
                recover_thread=recover_thread,
            )
            warnings.extend(thread_warnings)
            return 0, 0, threads, warnings

    project = await project_repo.create(
        name=name,
        instructions=str(legacy.get("summary") or ""),
        presentation={_LEGACY_PRESENTATION_KEY: legacy_id},
        user_id=user_id,
    )
    project_id = str(project["id"])
    logger.info("imported project %r as %s", name, project_id)

    documents = 0
    for material in legacy.get("materials") or []:
        if not isinstance(material, dict):
            continue
        material_id = str(material.get("id") or "")
        filename = str(material.get("filename") or "")
        source = _material_source(base_dir, legacy_id, material_id) if material_id else None
        if source is None or not filename:
            warnings.append(f"project {name!r}: material {filename or material_id!r} has no readable file — skipped")
            continue
        try:
            display_name = validate_shelf_filename(filename)
        except ValueError as exc:
            warnings.append(f"project {name!r}: material {filename!r} rejected — {exc}")
            continue
        payload = source.read_bytes()
        staged = await stage_document_bytes(
            paths,
            user_id=user_id,
            project_id=project_id,
            chunks=[payload],
            max_bytes=max_file_size,
        )
        result = await add_staged_document(
            document_repo,
            paths,
            user_id=user_id,
            project_id=project_id,
            name=display_name,
            staged=staged,
            source_kind="upload",
            source_name=display_name,
        )
        if result is None:
            warnings.append(f"project {name!r}: material {filename!r} was rejected by the shelf")
            continue
        _, created = result
        documents += 1
        logger.info("  material %r%s", filename, "" if created else " (deduplicated)")

    for output in legacy.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        title = str(output.get("title") or "").strip()
        if not title:
            continue
        note = str(output.get("note") or "")
        try:
            display_name = validate_shelf_filename(title)
        except ValueError as exc:
            warnings.append(f"project {name!r}: output {title!r} rejected — {exc}")
            continue
        payload = _output_body(title, note)
        staged = await stage_document_bytes(
            paths,
            user_id=user_id,
            project_id=project_id,
            chunks=[payload],
            max_bytes=max_file_size,
        )
        result = await add_staged_document(
            document_repo,
            paths,
            user_id=user_id,
            project_id=project_id,
            name=display_name,
            staged=staged,
            source_kind="output",
            source_name=title,
        )
        if result is None:
            warnings.append(f"project {name!r}: output {title!r} was rejected by the shelf")
            continue
        _, created = result
        documents += 1
        logger.info("  output %r%s", title, "" if created else " (deduplicated)")

    threads, thread_warnings = await _attach_threads(
        thread_repo=thread_repo,
        legacy=legacy,
        project_id=project_id,
        project_name=name,
        user_id=user_id,
        recover_thread=recover_thread,
    )
    warnings.extend(thread_warnings)

    return 1, documents, threads, warnings


async def import_legacy_projects(
    *,
    project_repo: ProjectRepository,
    document_repo: ProjectDocumentRepository,
    thread_repo: ThreadMetaRepository,
    paths: Paths,
    base_dir: Path,
    user_id: str,
    max_file_size: int = _DEFAULT_MAX_FILE_SIZE,
    recover_thread: ThreadRecovery | None = None,
) -> LegacyImportReport:
    """Import every legacy project under ``base_dir`` into the SQL store.

    Idempotent: a project whose legacy id is already recorded in
    ``presentation`` is skipped, so running this twice imports nothing the
    second time.

    ``recover_thread`` decides whether a conversation that lost its
    ``threads_meta`` row is still recoverable from the checkpointer; when it
    returns True the row is recreated and the thread attached.
    """
    report = LegacyImportReport()
    for legacy in _legacy_projects(base_dir):
        projects, documents, threads, warnings = await _import_project(
            project_repo=project_repo,
            document_repo=document_repo,
            thread_repo=thread_repo,
            paths=paths,
            base_dir=base_dir,
            legacy=legacy,
            user_id=user_id,
            max_file_size=max_file_size,
            recover_thread=recover_thread,
        )
        report.projects += projects
        report.documents += documents
        report.threads += threads
        report.warnings.extend(warnings)
    return report


async def _run(args: argparse.Namespace) -> int:
    config = get_app_config()
    db_backend = getattr(config.database, "backend", None)
    if db_backend not in ("sqlite", "postgres"):
        logger.error(
            "database.backend is %r; this importer needs 'sqlite' or 'postgres'. Set it in config.yaml (the same database the gateway uses).",
            db_backend,
        )
        return 1

    base_dir = get_paths().base_dir
    legacy_projects = _legacy_projects(base_dir)
    if not legacy_projects:
        logger.info("No legacy projects found in %s — nothing to import.", base_dir / "projects.json")
        return 0

    user_id = args.user_id or get_effective_user_id()
    paths = Paths(base_dir=base_dir)
    max_file_size = getattr(getattr(config, "uploads", None), "max_file_size", _DEFAULT_MAX_FILE_SIZE) or _DEFAULT_MAX_FILE_SIZE

    if args.dry_run:
        logger.info("Dry run — nothing will be written.")
        for legacy in legacy_projects:
            _report_dry_run(legacy)
        logger.info(
            "Dry run: %d project(s) would be imported. Legacy files are left in place.",
            len(legacy_projects),
        )
        return 0

    # The Gateway resolves ``database.sqlite_dir`` relative to its own working
    # directory (``backend/``). Anchor it the same way so this script never
    # writes to a different database than the gateway reads.
    db_config = config.database
    if db_config.backend == "sqlite" and not Path(db_config.sqlite_dir).is_absolute():
        backend_dir = Path(__file__).resolve().parents[1]
        db_config = db_config.model_copy(update={"sqlite_dir": str((backend_dir / db_config.sqlite_dir).resolve())})
    await init_engine_from_config(db_config)

    session_factory = get_session_factory()
    if session_factory is None:
        logger.error("The ORM engine is not initialised — cannot write to the project store.")
        return 1

    project_repo = ProjectRepository(session_factory)
    document_repo = ProjectDocumentRepository(session_factory)
    thread_repo = ThreadMetaRepository(session_factory)

    report = await import_legacy_projects(
        project_repo=project_repo,
        document_repo=document_repo,
        thread_repo=thread_repo,
        paths=paths,
        base_dir=base_dir,
        user_id=user_id,
        max_file_size=max_file_size,
        recover_thread=_thread_has_checkpoint,
    )

    for warning in report.warnings:
        logger.warning("%s", warning)

    logger.info(
        "Done: %d project(s), %d document(s), %d thread(s) imported into user %r. Legacy files left in place.",
        report.projects,
        report.documents,
        report.threads,
        user_id,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import legacy JSON workbench projects into the SQL project store.")
    parser.add_argument("--dry-run", action="store_true", help="List what would be imported without writing to the database.")
    parser.add_argument("--user-id", default="", help="Owner for the imported projects (defaults to the effective runtime user).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
