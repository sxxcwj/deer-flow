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

Workbench text search over upstream's projects, their shelf documents, and the
firm-methods catalogue. `GET /api/search?q=...`. Bounded to 20 hits.

- `project` — name and `instructions` of upstream's projects
- `material` — shelf documents with `source_kind == "upload"`
- `output` — shelf documents with `source_kind == "output"` (deliverables
  promoted from a thread's artifacts)
- `method` — entries in `methods.json`

Projects and documents are read through upstream's owner-scoped repositories
(`app.state.project_repo` / `app.state.project_document_repo`), so the results
respect the caller's permissions. When no database is configured the endpoint
still serves the `method` kind instead of failing.

### Projects

**Use the upstream implementation.** `app/gateway/routers/projects.py`,
`deerflow/persistence/projects/`, `deerflow/projects/context.py` and the
`/api/projects` endpoints are upstream's, backed by SQL with a document shelf,
trash retention, LLM summaries and owner-scoped authorization. They are
mounted by `app/gateway/app.py`; do **not** register a second `/api/projects`
router.

The consulting delivery views map onto upstream's model rather than replacing
it: a project's `instructions` is the consultation brief, shelf documents with
`source_kind == "upload"` are the materials, documents with
`source_kind == "output"` are the deliverables, and
`/workspace/projects/[id]` (upstream's) carries the document shelf, the
attached conversations and the new-chat button. The workbench adds only a
list page — `frontend/src/components/workspace/projects/workbench-projects-page.tsx` —
that links into it. Starting a conversation from a project attaches it to that
project: upstream's `chat-page.tsx` passes the `?project=` query parameter to
`createThread`.

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
