# 长伴咨询 Workbench 前端扩展

> 本文件是长伴咨询对上游 DeerFlow 前端的定制说明，不属于上游 AGENTS.md 继承链
> （`frontend/AGENTS.md` 距 32KB 硬上限只剩百余字节，放不下长伴内容；
> 见 `scripts/check_agent_guidance.py`）。

上游提供通用智能体平台。这些是叠加在上面的咨询公司定制，**不是上游功能**——
同步上游时不要删掉，每次同步后要重新贴回来。

后端的对应说明在 [../../backend/docs/WORKBENCH.md](../../backend/docs/WORKBENCH.md)。

## 品牌与文案

工作台是长伴咨询内部使用的工具，面向的是咨询顾问和 HR 团队，不是公开产品。
所有用户可见的品牌位都换成了长伴的：

| 位置 | 长伴 |
|---|---|
| 根布局 metadata | `src/app/layout.tsx` —— title「长伴咨询」、description「每个高成长企业背后，都有长伴相随。」 |
| 品牌 logo | `public/images/changban-logo.png`（1182×332 透明底 PNG），只用在落地页的导航左上角 |
| 品牌落地页 | `src/app/page.tsx` → `src/components/changban/promo-page.tsx`（取代上游 `components/landing/` 的首页） |
| 页面标题后缀 | `core/i18n/locales/*.ts` 的 `pages.appName`（驱动所有「xxx - 长伴咨询」标题） |
| 欢迎页 | 同上 `welcome.description` / `welcome.createYourOwnSkill*` |
| 登录 / 首次建管理员 | `src/app/(auth)/login/page.tsx`、`src/app/(auth)/setup/page.tsx` 的 h1 |
| 通知文案 | 同上 `notifications.*`（含测试通知标题） |
| 文档预览窗标题 | `core/artifacts/viewer.ts` 的 `artifactViewerTitle(filepath, appName)` —— 品牌名由调用方传入，不写死 |
| 设置里的「关于」 | `src/components/workspace/settings/about-content.ts`（内联 markdown，保留对上游的出处说明） |

i18n 里的长伴块（`workbench` / `methods` / `search` 三个顶层块，以及
`agents.avatar*`、`sidebar.home/projects/methods`、`workspace.phone`）直接
追加在两个 locale 文件的**末尾**——上游同步时这一段最容易冲突，冲突时以
上游 locale 为基线重新贴回。

`src/components/workspace/settings/about.md` 是上游的旧文件，已经没有引用
（`about-settings-page.tsx` 用的是 `about-content.ts`），留着只是上游源码。

## 工作台页面

- `src/components/workspace/projects/workbench-projects-page.tsx` —— 长伴的
  项目列表页，挂在 `/workspace/projects`。项目详情、文档架、挂接会话用的是
  上游的 `/workspace/projects/[id]`，不要另起一套。
- `src/components/workspace/workbench-shell.css` —— `cb-shell` 主题。

## 不要改的地方

- 内部标识符（`deerflow:` 开头的 localStorage key、`deerflow_project_id`
  元数据键、`deerflow-memory-*.json` 文件名）是上游契约，改了会丢数据。
- 上游的 `components/landing/`、`content/`（文档站）、`/blog` 路由是上游的
  公开内容页，工作台里没有入口链接它们。它们仍显示 "DeerFlow" 属于预期。
