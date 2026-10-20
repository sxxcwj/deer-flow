"""Read a short project brief for the current conversation.

The workbench stores projects in ``{base_dir}/projects.json``. This module only
reads that file. It does not import the gateway.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_BRIEF_LIMIT = 6000
_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def format_project_brief(
    base_dir: Path,
    *,
    thread_id: str | None = None,
    project_id: str | None = None,
) -> str:
    """Return a bounded brief for the project tied to this conversation."""
    project = _find_project(base_dir, thread_id=thread_id, project_id=project_id)
    if project is None:
        return ""
    body = _render(base_dir, project)
    if not body:
        return ""
    if len(body) > _BRIEF_LIMIT:
        body = body[:_BRIEF_LIMIT].rstrip() + "\n…"
    return f"<project_context>\n{body}\n</project_context>"


def _find_project(base_dir: Path, *, thread_id: str | None, project_id: str | None) -> dict | None:
    path = base_dir / "projects.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read projects.json")
        return None
    if not isinstance(raw, list):
        return None
    if thread_id:
        for item in raw:
            if isinstance(item, dict) and thread_id in (item.get("thread_ids") or []):
                return item
    if project_id:
        for item in raw:
            if isinstance(item, dict) and item.get("id") == project_id:
                return item
    return None


def _render(base_dir: Path, project: dict) -> str:
    name = str(project.get("name") or "").strip()
    if not name:
        return ""
    lines = [
        "本对话属于一个本地项目。回答时只用这里写下的内容，不要补写没有出现的客户、合同或数字。",
        "",
        f"项目：{name}",
    ]
    summary = str(project.get("summary") or "").strip()
    if summary:
        lines.append(f"说明：{summary}")

    notes = []
    for output in (project.get("outputs") or [])[:5]:
        if not isinstance(output, dict):
            continue
        title = str(output.get("title") or "").strip()
        if not title:
            continue
        note = str(output.get("note") or "").strip()
        notes.append(f"- {title}" + (f"：{note}" if note else ""))
    if notes:
        lines.extend(["", "最近记录：", *notes])

    material_lines = _material_lines(base_dir, project)
    if material_lines:
        lines.extend(["", "材料：", *material_lines])
    return "\n".join(lines)


def _material_lines(base_dir: Path, project: dict) -> list[str]:
    project_id = str(project.get("id") or "")
    if not _ID_RE.fullmatch(project_id):
        return []
    directory = base_dir / "projects" / project_id / "materials"
    lines: list[str] = []
    for material in project.get("materials") or []:
        if not isinstance(material, dict):
            continue
        material_id = str(material.get("id") or "")
        filename = str(material.get("filename") or "").replace("\n", " ").strip()
        if not _ID_RE.fullmatch(material_id) or not filename:
            continue
        lines.append(f"### {filename}")
        excerpt_path = directory / f"{material_id}.excerpt.txt"
        if excerpt_path.is_file():
            try:
                excerpt = excerpt_path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                excerpt = ""
            if excerpt:
                lines.append(excerpt)
        lines.append("")
    return lines
