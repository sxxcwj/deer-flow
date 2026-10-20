"""Read a short methods brief for any conversation."""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_BRIEF_LIMIT = 4000
_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def format_methods_brief(base_dir: Path) -> str:
    """Return a bounded brief of firm methods. Empty when none are stored."""
    path = base_dir / "methods.json"
    if not path.is_file():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read methods.json")
        return ""
    if not isinstance(raw, list) or not raw:
        return ""
    lines = [
        "以下是公司自己的方法，不属于某一个项目。回答时可以引用，不要把这里没有写的内容说成已经确定的口径。",
        "",
    ]
    directory = base_dir / "methods"
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        lines.append(f"### {title}")
        body = str(item.get("body") or "").strip()
        if body:
            lines.append(body)
        method_id = str(item.get("id") or "")
        if _ID_RE.fullmatch(method_id):
            excerpt_path = directory / f"{method_id}.excerpt.txt"
            if excerpt_path.is_file():
                try:
                    excerpt = excerpt_path.read_text(encoding="utf-8", errors="replace").strip()
                except OSError:
                    excerpt = ""
                if excerpt:
                    lines.append(excerpt)
        lines.append("")
    body = "\n".join(lines).strip()
    if body.count("###") == 0:
        return ""
    if len(body) > _BRIEF_LIMIT:
        body = body[:_BRIEF_LIMIT].rstrip() + "\n…"
    return f"<method_context>\n{body}\n</method_context>"
