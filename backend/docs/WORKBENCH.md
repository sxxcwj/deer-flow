# 长伴咨询 Workbench 扩展

Upstream provides the general agent platform. These are the consulting-specific
additions layered on top of it. They are **not** upstream features — do not
remove them during upstream merges, and re-apply them after each sync.

> 本文件是长伴咨询对上游 DeerFlow 的定制说明，不属于上游 AGENTS.md 继承链
> （上游对继承链有 96KB 硬上限，见 `scripts/check_agent_guidance.py`）。

Upstream provides the general agent platform. These are the consulting-specific
additions layered on top of it. They are **not** upstream features — do not
remove them during upstream merges, and re-apply them after each sync.

### Methods (`/api/methods`)

Firm-wide methodologies (公司方法论) — reusable consulting口径 that belong to
the firm rather than to a single client project.

- Router: `app/gateway/routers/methods.py`; harness reader: `deerflow/methods/brief.py`
- Storage: `{base_dir}/methods.json` (list) + `{base_dir}/methods/{id}.excerpt.txt` (optional excerpt file)
- Endpoints: `GET /api/methods`, `POST /api/methods`, `DELETE /api/methods/{id}`, `GET /api/methods/{id}/file`
- `format_methods_brief()` renders a bounded brief (≤ 4000 chars) tagged
  `<method_context>`, explicitly instructing the model to cite these and not
  to present unwritten content as settled口径.

### Search (`/api/search`)

Local text search over methods, chat titles and other workbench records.
`GET /api/search?q=...&kind=...`. Bounded to 20 hits per kind.

**Known gap**: the `project` / `output` / `material` hit kinds still read the
retired `projects.json` layout, which upstream's database-backed project store
no longer writes — those kinds currently return nothing. The `method` kind
works. Re-point the project kinds at `project_repo` (owner-scoped, same
pattern as `app/gateway/routers/projects.py`) when the consulting delivery
views are ported onto upstream projects.

### Projects

**Use the upstream implementation.** `app/gateway/routers/projects.py`,
`deerflow/persistence/projects/`, `deerflow/projects/context.py` and the
`/api/projects` endpoints are upstream's, backed by SQL with a document shelf,
trash retention, LLM summaries and owner-scoped authorization. They are
mounted by `app/gateway/app.py`; do **not** register a second `/api/projects`
router.

Upstream also already renders project context into the model request:
`DynamicContextMiddleware.wrap_model_call` emits one transient, request-only
message per model call from a snapshot pinned at run admission
(`PROJECT_CONTEXT_KEY`), so nothing project-related is persisted to state or
checkpoints. A local `ProjectContextMiddleware` that mutated
`state["messages"]` would be a duplicate of that mechanism **and** would
reintroduce the per-turn accumulation this upstream design avoids.

### Agent Avatar

Custom agents may carry an emoji or an http(s) image URL.

- Field: `AgentConfig.avatar`; validation: `normalize_avatar()` in
  `deerflow/config/agents_config.py` (short emoji ≤ 32 chars, or an http(s)
  URL ≤ 2048 chars; anything else is rejected with HTTP 422)
- Exposed on `AgentResponse` / `AgentCreateRequest` / `AgentUpdateRequest`
- An empty string on update clears the avatar; an omitted field preserves it
- `setup_agent` and the `PUT /api/agents/{name}` route carry an existing
  avatar forward when other fields are edited
