# UME V1.0 完整功能开发与 MiniMax 严格执行手册

> 文档状态：开发执行稿  
> 基线日期：2026-10-12  
> 基线提交：`3bf062c`（`feat: add connector management functionality`）  
> 适用对象：使用 MiniMax 在本仓库继续完成 UME V1.0 的开发者  
> 上位文档：`UME-V1-PRD.md`、`UME-V1-TECHNICAL-IMPLEMENTATION.md`、`UME-P0-BASELINE-REPORT.md`

## 1. 文档目的

本文不是新的产品需求文档，而是从当前代码基线继续开发的执行手册。它用于解决以下问题：

1. 区分已经存在、部分完成、尚未开发和仅缺验证的能力。
2. 把剩余工作拆成可以单独测试、单独审查、单独回滚的小任务。
3. 为 MiniMax 提供可复制的总控提示词和逐阶段提示词。
4. 通过硬性门禁阻止跳步、伪造测试结果、扩大范围和一次性生成大量不可审查代码。
5. 将 PRD 第 11 节的验收标准转化为可运行、可留证据的测试与报告。

本文中的“完成”一律表示代码、测试、权限、迁移、文档和实际运行证据同时满足要求。仅生成代码、仅存在路由、仅有页面外壳或仅声称测试通过，都不算完成。

## 2. 权威来源与冲突处理

MiniMax 每次任务开始前必须按以下优先级读取规则：

1. 用户在当前任务中的明确要求。
2. 根目录 `AGENTS.md`。
3. 所编辑文件最近目录中的 `AGENTS.md`。
4. `docs/specs/UME-V1-PRD.md`。
5. `docs/specs/UME-V1-TECHNICAL-IMPLEMENTATION.md`。
6. 本执行手册。
7. 现有实现模式和测试约定。

若文档与实际代码不一致，不得静默选择其中一个。必须：

1. 用文件路径、符号或测试结果记录差异。
2. 判断是文档过时、代码偏离还是产品决策未完成。
3. 对不改变产品语义的小偏差，以当前代码模式为准并同步文档。
4. 对会改变公开 API、数据语义、权限或兼容性的差异，停止实现并请求决定。

## 3. 不可违反的仓库规则

MiniMax 在所有阶段都必须遵守：

- 编辑任何包前读取最近的 `AGENTS.md`。
- 不修改 `.github/workflows/`，除非维护者明确授权。
- 不创建 Pull Request，除非关联 issue 已有 `accepted` 标签且贡献者已自行签署 CLA。
- 不提交 `.env`、访问令牌、API Key、数据库密码、真实用户数据或生产日志。
- 不跳过 pre-commit hooks。
- TypeScript 包使用 pnpm；只有 `integrations/opencode-plugin/` 使用 Bun。禁止 npm 和 yarn。
- TypeScript 只使用 ES module `import`，禁止 `require()`。
- 根 Python/Server 遵守 Ruff 120；`cli/python/` 遵守 Ruff 100。
- `cli/node/` 使用 Biome、TypeScript 和 Vitest；不得套用其他包的 ESLint/Jest 配置。
- Dashboard 使用已有 Next.js、React、Tailwind、Radix、TanStack Table 和现有 API hooks；未经批准不引入新框架。
- Python 新依赖不得直接加入核心 `dependencies`；应使用合适的 optional group，并先确认确有必要。
- 公共 API 变化必须同一任务更新文档、OpenAPI/类型和相关客户端。
- Bug 修复必须先添加能复现问题的失败测试，再修复。
- 不允许把 xfail、skip、未运行或收集失败描述为“通过”。
- 不允许为了让测试变绿而删除断言、扩大 mock 边界、放松权限或吞掉异常。
- 不允许手工编辑由 `integrations/agent-plugin-core` 生成的插件 `core/` 或 `skills/` 目录。

## 4. 当前基线事实

以下内容是对基线提交的静态盘点，不替代每个阶段的实际测试。

### 4.1 已有后端主体

当前已存在：

- 工作区、成员和项目模型、仓储、服务及 API。
- 对话、消息、导入预览、导入任务、幂等与失败重试 API。
- 记忆业务投影、来源、版本、归档、恢复、遗忘和失败重试 API。
- 图谱边、邻居查询、时间线与 token 预算上下文 API。
- 连接器凭证、scope、撤销和认证解析。
- 审计事件模型和写入服务。
- Alembic 迁移 `001` 至 `013`。

这些能力必须重新运行相应测试后才能标记为已验收。存在文件或路由不等于端到端已完成。

### 4.2 已有 Dashboard 页面

当前已有工作区、项目、对话列表、对话详情、记忆列表等页面。旧基线报告中“Dashboard 基础页面仍未实现”的结论已经部分过时。

### 4.3 明确缺口

当前仍需实现或收口：

1. Dashboard 总览、记忆详情、图谱、时间线、连接器、统一导入导出和审计页面。
2. 工作区导出 API、导出任务、下载格式及跨工作区隔离。
3. 备份、恢复、恢复验证和运维文档。
4. 审计查询 API、筛选、分页和管理界面。
5. Python 与 Node CLI 的本地 Server profile、路由和认证对齐。
6. CLI 的 `workspace/project/conversation/memory/context/connector/export/backup` 命令族。
7. 独立、统一、可发布的 `integrations/ume-mcp`。
8. Dashboard 自动化测试和关键旅程 E2E。
9. 完整安全矩阵、日志脱敏、性能基准及发布验收报告。
10. SDK `chat()` 仍未实现，但它不是 V1 主链路的默认阻塞项；除非产品明确纳入范围，不得顺手实现。

### 4.4 已实现但仍需专项复验

- 连接器撤销是否对已有凭证立即生效。
- 项目绑定连接器是否无法跨项目访问。
- 记忆来源和版本恢复是否保持审计、状态与引擎一致。
- 图谱、时间线、上下文接口是否在所有资源 ID 路径上关闭跨工作区访问。
- 对话导入的 100 条以上消息、重复导入和并发幂等性。
- 空库迁移和从现有基线数据库升级。
- Docker Compose 中 API、PostgreSQL、pgvector、Neo4j 和 Dashboard 的真实启动。

## 5. V1.0 目标架构边界

V1.0 必须保持以下边界：

- FastAPI 是自托管业务 API 入口，业务路由位于 `/api/ume/v1`。
- PostgreSQL 保存身份、工作区、项目、对话、来源、版本、关系、任务和审计等业务数据。
- `ume.Memory` / `AsyncMemory` 通过 Memory Engine Adapter 提供记忆引擎能力。
- V1.0 不新增独立图数据库作为 UME 业务关系层的强依赖。
- Dashboard 只消费服务端权限裁决后的数据；前端隐藏按钮不是权限控制。
- CLI 和 MCP 必须调用相同的服务端业务语义，不能分别实现另一套权限或状态机。
- 导出、备份和恢复必须保持工作区边界，并记录可审计事件。
- 长任务可以先使用现有 import-job 风格的数据库状态机；未经批准不得引入新的队列框架。

## 6. 统一 API 与错误约定

新增 V1 API 必须复用当前统一响应封装：

```json
{
  "data": {},
  "error": null,
  "request_id": "..."
}
```

错误响应必须：

- 使用稳定的 HTTP 状态码和机器可识别错误代码。
- 不泄露数据库、文件路径、密钥、哈希、令牌前缀之外的信息。
- 对无权限资源优先返回现有安全模型规定的 `404`，避免资源枚举。
- 校验错误明确指出字段，但不回显敏感值。
- 保留 `request_id` 便于审计和排错。

所有列表接口应统一支持：

- 稳定排序。
- cursor 分页，而不是不受限的全表返回。
- 明确的最大 `limit`。
- 空结果、非法 cursor 和已删除资源测试。
- workspace/project 过滤在 Repository 或更低数据访问层生效。

## 7. 数据库与迁移原则

每个新增持久化功能必须：

1. 创建新的连续 Alembic revision，不修改已经发布的旧 migration。
2. 同步 SQLAlchemy 模型、索引、唯一约束和外键策略。
3. 包含空库 `upgrade head` 测试。
4. 包含从当前 `013` 升级到 head 的测试。
5. 对可逆结构提供 downgrade，并真实执行升级、降级、再升级。
6. 对大量数据路径避免逐行 N+1 查询。
7. 明确删除语义：软删除、墓碑、硬删除和备份保留不能混用。

建议后续迁移编号：

- `014_create_export_jobs.py`
- `015_add_backup_restore_metadata.py`，仅在确实需要业务元数据时创建

编号必须先检查仓库现状，若已被占用则顺延。

## 8. 严格阶段门禁

开发严格按 M0 至 M12 顺序执行。一个阶段未满足退出条件时，不得开始下一阶段，也不得把下一阶段代码混入当前 diff。

| 阶段 | 内容 | 主要产物 |
| --- | --- | --- |
| M0 | 基线复核 | 最新状态矩阵与可重复测试证据 |
| M1 | Dashboard 数据层与共用状态 | 类型、端点、分页和错误组件 |
| M2 | 记忆详情与来源版本 UI | 记忆详情页面 |
| M3 | 图谱、时间线与上下文 UI | 三个业务视图 |
| M4 | 连接器与审计查询 | API、页面、安全测试 |
| M5 | 工作区导出 | 迁移、任务、API、下载、页面 |
| M6 | 备份与恢复 | 脚本、校验、文档、演练证据 |
| M7 | CLI 本地 profile 与基础记忆契约 | 两套 CLI 对齐基础 API |
| M8 | CLI V1 业务命令 | 完整命令族与契约测试 |
| M9 | 统一 MCP Server | `integrations/ume-mcp` |
| M10 | Dashboard E2E | Playwright 关键旅程 |
| M11 | 安全、性能和可靠性 | 测试矩阵与基准报告 |
| M12 | 发布验收 | PRD 验收报告、部署升级文档 |

## 9. M0：重新建立可信基线

### 9.1 目标

消除旧报告与当前代码之间的偏差，确认哪些能力真实可用，避免重复开发。

### 9.2 必做步骤

1. 读取根和 `server/` 的 `AGENTS.md`。
2. 记录当前分支、提交、dirty 状态、Python、Node、pnpm、Docker 和 Compose 版本。
3. 列出 `/api/ume/v1` 的全部路由，并与技术文档 §9.3 对照。
4. 列出 Dashboard 的全部实际页面路由。
5. 运行现有 `server/tests/ume` 测试；不可用依赖必须如实记录。
6. 在 Docker 可用时执行 Compose 启动和 P0 smoke。
7. 重新检查 CLI contract 的 pass/xfail 数量。
8. 更新基线报告，保留历史结论并新增“2026-10-12 后复核”章节，不抹除旧证据。

### 9.3 退出条件

- 每个 PRD 功能都有 `完成/部分完成/未实现/受阻` 状态。
- 每个“完成”都有测试命令和结果。
- 每个“受阻”都有错误原文、环境条件和后续归属。
- 未修改任何业务功能。

## 10. M1：Dashboard 数据层与共用状态

### 10.1 目标

建立所有新页面复用的强类型 V1 API 客户端，禁止每个页面自行拼 URL 和解析错误。

### 10.2 实现要求

- 扩展 `server/dashboard/src/utils/ume-api.ts` 和相关类型。
- 覆盖 memory detail、sources、versions、graph、neighbors、timeline、context、connectors、audit 和 export。
- 建立统一 envelope 解包、认证过期、请求取消和错误映射。
- 建立 cursor 分页状态。
- 复用 loading、empty、error、retry、forbidden/not-found 状态组件。
- 不在客户端复制角色权限矩阵；服务端仍为真源。
- 对 URL、query 参数和响应解析添加单元测试。若当前 Dashboard 没有测试框架，先提出最小方案并获得确认，不得擅自引入大型框架。

### 10.3 退出条件

- `pnpm run typecheck`、`pnpm run lint`、`pnpm run build` 通过。
- 新页面尚未实现，diff 只包含共用数据层和必要测试。
- 无重复 API 封装。

## 11. M2：记忆详情、来源和版本页面

### 11.1 页面

新增 `/dashboard/memories/[id]`，至少包含：

- 当前正文、状态、类型、创建时间、更新时间和项目。
- 来源消息列表，可跳转到对话详情并定位消息。
- 版本时间线和相邻版本差异。
- 编辑、归档、恢复、遗忘和失败重试操作。
- 危险操作二次确认。
- 操作成功后的缓存刷新和错误恢复。

### 11.2 安全与一致性

- 页面不能依赖 URL 中的 workspace ID 绕过后端检查。
- 已归档、已遗忘、写入失败等状态只展示合法操作。
- 恢复历史版本必须产生新版本，不覆盖历史行。
- 永久遗忘必须验证引擎删除与业务墓碑状态。

### 11.3 测试

- 服务端补足来源、版本、恢复和跨工作区测试。
- 页面覆盖 loading、empty、404、403/安全 404、失败重试和成功流程。
- 手工验证至少一条“对话消息 → 记忆来源 → 历史版本 → 恢复”链路。

## 12. M3：图谱、时间线和上下文页面

### 12.1 图谱

新增 `/dashboard/graph`：

- 初始最多加载 100 个节点。
- 单次邻居展开最多 50 个。
- 按稳定 ID 去重节点和边。
- 支持创建、编辑和删除关系。
- 节点详情按需加载，不在图谱载荷中返回完整敏感正文。
- 大图必须保持可操作，不允许一次拉取全工作区。

优先使用仓库已有依赖。若没有合适的图可视化能力，先输出技术选择记录，比较实现复杂度、bundle 大小、维护性和许可证，等待批准后再加依赖。

### 12.2 时间线

新增 `/dashboard/timeline`：

- 合并消息和记忆事件。
- 支持项目、时间范围和事件类型筛选。
- 稳定 cursor 分页。
- 能跳转到对话或记忆详情。

### 12.3 上下文调试器

可作为独立页或图谱页中的明确区域：

- 输入 query、project 和 token budget。
- 展示入选项、丢弃项、得分、token 估算和原因。
- 明确显示实际使用预算不超过请求预算。
- 展示来源引用。

## 13. M4：连接器和审计

### 13.1 审计查询 API

新增只读审计 API，建议：

```text
GET /api/ume/v1/audit-events
```

查询参数至少支持 `workspace_id`、`project_id`、`actor_type`、`actor_id`、`action`、`resource_type`、`resource_id`、时间范围、cursor 和 limit。

要求：

- 只有工作区 owner/admin 或明确具备审计权限的主体可访问。
- 连接器不得获得审计管理能力。
- 返回事件时脱敏 credential、Authorization、Cookie、密码和正文中的秘密字段。
- 审计查询本身是否记录访问事件应遵守 PRD 决策；未决定时停止询问。

### 13.2 Dashboard 页面

新增：

- `/dashboard/connectors`
- `/dashboard/audit`

连接器页面支持创建、scope 选择、一次性显示明文凭证、复制提示、修改和撤销。明文凭证不得写入 localStorage、日志或后续 GET 响应。

审计页面支持筛选、分页、资源跳转和 JSON 详情，但默认折叠 metadata。

### 13.3 强制安全测试

- 普通成员不能创建或撤销连接器。
- 连接器不能授予超出 allowlist 的 scope。
- 项目级连接器不能访问另一个项目。
- 撤销后下一次请求立即 401/403，不接受缓存宽限。
- 日志和审计 metadata 不包含明文凭证。

## 14. M5：工作区导出

### 14.1 产品范围

实现一个工作区范围、可审计、可重试的异步导出。默认格式为版本化 JSON，不在 V1 同时支持多个复杂格式。

建议 API：

```text
POST /api/ume/v1/exports
GET  /api/ume/v1/exports/{job_id}
GET  /api/ume/v1/exports/{job_id}/download
POST /api/ume/v1/exports/{job_id}/retry
```

### 14.2 导出内容

- manifest：格式版本、导出时间、工作区 ID、计数和校验和。
- workspace 和 projects。
- conversations 和 messages。
- memory records、projects、sources 和 versions。
- edges。
- connectors 只导出元数据和 scope，绝不导出 credential hash 或明文。
- audit 是否包含由产品决策确定；默认不包含敏感 metadata。

### 14.3 实现约束

- 复用 import-job 的状态机和幂等模式，不引入队列框架。
- 文件写入临时路径后原子完成，失败时不提供半成品下载。
- 提供大小、行数/对象数和 SHA-256 校验。
- 下载必须重新鉴权，不能只凭不可撤销的永久 URL。
- 测试跨工作区 job ID、下载 ID 和伪造路径。
- 明确临时文件保留周期和清理策略。

### 14.4 Dashboard

新增 `/dashboard/import-export`，整合已有导入能力和新导出任务。展示状态、进度、失败原因、重试和下载。

## 15. M6：备份与恢复

### 15.1 范围

备份是部署级运维能力，不等同于工作区 JSON 导出。V1 至少覆盖 PostgreSQL；如 Neo4j 或文件存储保存不可重建数据，也必须纳入或明确可重建流程。

### 15.2 必须产物

- `server/scripts/backup.sh` 或与当前环境一致的脚本。
- `server/scripts/restore.sh`。
- 输入校验、目标确认和非交互 CI 模式。
- 备份 manifest、版本、数据库 schema revision、创建时间、校验和。
- 恢复前兼容性检查。
- 恢复到空环境的演练步骤。
- 恢复后 smoke：认证、工作区、项目、消息计数、记忆计数、来源、版本、边和审计。
- `docs/open-source/` 中部署、升级、备份与恢复文档；新增 `.mdx` 必须更新 `docs.json` 和 `llms.txt`。

### 15.3 安全

- 备份不得默认写入仓库。
- 命令不得回显密码。
- 恢复是破坏性操作，必须检查明确目标并要求显式确认。
- 测试只操作专用临时数据库或 Compose 测试栈。

## 16. M7：CLI 本地 profile 和基础契约

### 16.1 目标

先让现有记忆命令可靠调用本地 Server，再扩展新命令族。

### 16.2 设计

扩展 `cli/cli-spec.json`：

- `hosted` profile 保持现有行为。
- `local` profile 默认地址 `http://localhost:8888`，但允许用户配置。
- 明确认证 header、scheme、方法、路径、尾斜杠和响应 envelope。
- Python 和 Node CLI 都从同一契约导出或读取等价配置，不允许手写两套漂移表。

### 16.3 顺序

1. 将现有 11 个 xfail 契约逐个转成真实失败测试。
2. 仅修复 profile、URL、认证和 envelope。
3. 保持 Hosted 行为回归测试。
4. Python CLI 与 Node CLI 对相同输入构造相同请求。
5. xfail 在对应能力修好后必须删除；XPASS 不是最终状态。

### 16.4 测试命令

Python CLI：

```bash
cd cli/python
ruff check .
ruff format --check .
pytest
hatch build
```

Node CLI：

```bash
cd cli/node
pnpm run lint
pnpm run typecheck
pnpm run test
pnpm run build
```

## 17. M8：CLI V1 业务命令

按以下顺序分小任务实现，每一个命令族单独提交与验收：

1. `ume workspace list/get/create/update/delete/member ...`
2. `ume project list/get/create/update/delete`
3. `ume conversation list/get/create/import/messages`
4. `ume memory add/search/get/list/update/archive/restore/forget/sources/versions`
5. `ume context build`
6. `ume connector list/get/create/update/revoke`
7. `ume export create/status/download/retry`
8. `ume backup` 只做本地运维脚本的安全包装；若无法安全实现则只提供文档，不远程暴露恢复。

要求：

- 旧的 `ume add/search/get/list/update/delete` 保留为兼容别名。
- 人类模式提供清晰表格，agent 模式提供稳定 JSON envelope。
- stdout 只输出结果，诊断和进度写 stderr。
- 非交互模式不得弹出确认；危险操作要求显式 `--yes`。
- `--workspace-id`、`--project-id`、profile 和 token 的优先级明确且两端一致。
- 每个命令族都有 Python/Node parity 测试。

## 18. M9：统一 MCP Server

### 18.1 包结构

新建 `integrations/ume-mcp/`，开始前再次读取 `integrations/AGENTS.md`。MCP 不应复制编辑器插件全部代码，应复用可稳定复用的协议和客户端层；若共享代码会形成不合理耦合，保持小型独立实现。

### 18.2 V1 工具

至少提供：

- `memory_add`
- `memory_search`
- `memory_get`
- `memory_context`
- `memory_sources`

可选只读发现工具：

- `workspace_list`
- `project_list`

写管理工具不应默认暴露。

### 18.3 每个工具的要求

- 完整 JSON Schema。
- 字符串、数组、limit、token budget 和 metadata 大小限制。
- 明确超时。
- 结构化错误，不向模型泄露 token 或内部 traceback。
- 使用 connector credential 和最小 scope。
- `X-UME-Source`、`X-Application`、`X-UME-Client` 遵守集成归因规则。
- stdout 仅 MCP 协议，日志写 stderr。
- 离线单元测试，不依赖真实托管平台。

### 18.4 验收

- Codex 和至少另一个 MCP 客户端连接同一本地 Server。
- 客户端 A 写入记忆，客户端 B 在同一项目检索到。
- 项目外检索失败。
- 撤销 connector 后两个客户端下一次请求立即失败。

## 19. M10：Dashboard 自动化测试

若仓库仍未配置 Playwright，先提出最小配置变更清单，等待批准后实施。不得修改 `.github/workflows/`。

关键旅程：

1. 首次注册和登录。
2. 创建工作区和项目。
3. 导入 100 条消息并等待任务完成。
4. 重复导入，消息数不增加。
5. 打开记忆详情、来源和版本。
6. 恢复历史版本。
7. 打开图谱并展开邻居。
8. 运行 token-budgeted context。
9. 创建连接器、复制一次性 token、撤销。
10. 创建导出并下载。
11. 普通成员看不到且无法调用管理操作。

测试必须使用专用测试数据和稳定选择器，不依赖文本位置或随机 sleep。

## 20. M11：安全、性能与可靠性

### 20.1 安全矩阵

对每个资源和动作至少覆盖：owner、admin、editor、viewer、workspace connector、project connector、revoked connector、无凭证和跨工作区用户。

资源包括：

- workspace/member/project
- conversation/message/import job
- memory/source/version
- graph/timeline/context
- connector
- audit
- export/download

必须测试直接伪造 UUID、cursor、project ID、job ID 和嵌套资源 ID。

### 20.2 日志脱敏

扫描并测试以下内容不出现在日志、错误、审计 metadata 和遥测中：

- Authorization/Cookie
- API Key 和 connector credential
- password/refresh token
- 数据库连接串中的密码
- 导出下载内部路径

### 20.3 性能基线

在可重复环境记录：

- 导入 100、1,000 和 10,000 条消息。
- 10k/100k 记忆下的列表和搜索。
- 图谱初始 100 节点和邻居 50 节点。
- 8k token budget 的上下文组装。
- 工作区导出大小和耗时。

报告必须包含硬件、容器资源、数据生成方式、样本次数、p50/p95 和失败率。没有实际测量不得填写数字。

### 20.4 可靠性

- 导入和导出失败可重试且不重复数据。
- 引擎失败时业务状态可观察、可恢复。
- 服务重启后任务状态不丢失。
- 恢复备份后 migration head 与数据校验通过。

## 21. M12：发布验收

创建新的 V1 验收报告，不覆盖历史基线报告。逐条复制 PRD §11 的 checkbox，并为每项填写：

- 状态：PASS/FAIL/BLOCKED/NOT RUN。
- 对应提交。
- 测试命令。
- 结果摘要。
- 日志或报告路径。
- 已知限制。

发布前必须：

1. 工作树中没有意外文件、凭证、构建产物或无关格式化。
2. 所触及包的 lint、typecheck、unit、integration、build 全部运行。
3. Docker Compose 从干净 volume 启动。
4. 数据库从空库升级到 head。
5. 从基线 revision 升级到 head。
6. 执行备份、销毁测试环境数据、恢复和 smoke。
7. 执行完整安全矩阵。
8. 执行 Dashboard E2E。
9. 验证 CLI Python、CLI Node、MCP 三种客户端。
10. 更新公开文档与命令示例。

## 22. MiniMax 总控提示词

将下面整段作为每个新会话的第一条提示词。只替换方括号中的任务信息。

```text
你正在 D:\github\mem0 的 UME 单体仓库中工作。

本次唯一任务：[填写 M 阶段和任务，例如“M4.1 实现审计查询 API”]

必须严格执行以下规则：

1. 开始前完整读取根 AGENTS.md、目标文件最近目录的 AGENTS.md，以及：
   - docs/specs/UME-V1-PRD.md
   - docs/specs/UME-V1-TECHNICAL-IMPLEMENTATION.md
   - docs/specs/UME-V1-MINIMAX-DEVELOPMENT-PLAYBOOK.md
2. 先执行只读检查：git status --short、相关文件、现有测试和现有实现模式。不要假设文档状态仍然正确。
3. 先给出不超过 12 项的执行清单，逐项标注将修改的文件、测试和验收条件。
4. 本次只完成指定任务。不得提前实现下一阶段，不得顺手重构，不得修改 .github/workflows/。
5. 若工作树已有用户修改，必须保留并绕开；不得 reset、checkout 或覆盖。
6. Bug 修复先写能失败的回归测试并运行确认失败。新功能先写契约/权限/边界测试，再写实现。
7. 每完成一个小步骤立即运行最小相关测试。全部实现后运行目标包完整 lint、typecheck、test 和 build。
8. 任何测试未运行、跳过、xfail、收集失败或依赖缺失，都必须如实报告，禁止写成通过。
9. 不得创建或提交 .env、密钥、真实凭证、生产数据。不得在输出中打印秘密。
10. 不引入新框架、数据库、队列或大型依赖。若确实需要，停止实现，给出选项和影响，等待确认。
11. 公共 API、schema 或 CLI 行为变化必须同步测试、类型和文档。
12. 权限必须在服务端和 Repository/数据访问层实施，不能只靠前端隐藏。
13. 跨工作区、伪造 ID、撤销凭证和敏感信息脱敏是强制测试项。
14. 不允许删除断言、放宽校验、吞异常、扩大 mock 或使用假实现来让测试变绿。
15. 没有满足本任务退出条件时不得宣称完成，也不得进入下一任务。

执行方式：
A. 读取规则和代码。
B. 输出当前事实、差距和计划。
C. 添加并运行测试，记录预期失败。
D. 实现最小改动。
E. 运行最小测试并修复。
F. 运行目标包完整检查。
G. 检查 git diff，确认没有无关修改和秘密。
H. 按固定格式交付报告。

固定交付报告：
- 任务：
- 状态：PASS / FAIL / BLOCKED / PARTIAL
- 已实现行为：
- 修改文件：
- 数据库迁移：
- 权限与安全验证：
- 实际运行命令及逐项结果：
- 未运行项目及原因：
- 已知风险：
- git diff 摘要：
- 是否满足退出条件：是/否，并逐条说明
- 下一阶段建议：只描述，不实施

如果需求、权限语义、数据删除策略或公开 API 存在歧义，立即停止在决策点，不要自行猜测。
```

## 23. 分阶段追加提示词

总控提示词之后，再追加对应阶段文本。

### 23.1 M0 追加提示词

```text
只执行 M0 基线复核。禁止修改业务代码。用实际路由、页面、迁移和测试结果更新基线状态矩阵。保留旧报告历史，不得为了状态好看删除失败。Docker 不可用时记录原始错误和 BLOCKED，不得伪造 smoke 结果。
```

### 23.2 M1 追加提示词

```text
只建立 Dashboard V1 共用 API 数据层、类型和状态组件。不要创建业务页面。必须复用现有 hooks 和样式；先检查是否已有等价工具。最终必须运行 Dashboard 的 typecheck、Prettier check 和 production build。
```

### 23.3 M2 追加提示词

```text
只实现记忆详情、来源、版本和合法状态操作。先验证后端接口契约与权限测试，不得在页面中补写业务规则。恢复历史版本必须新增版本；遗忘必须遵守引擎与墓碑一致性。不得实现图谱或导出。
```

### 23.4 M3 追加提示词

```text
只实现图谱、时间线和上下文调试 UI。严格执行初始 100 节点、单次 50 邻居、cursor 分页和 token budget。未经批准不得增加图形库；如果现有依赖无法满足，停止并提交技术选择记录。
```

### 23.5 M4 追加提示词

```text
只实现审计查询 API、连接器页面和审计页面。明文连接器 credential 只能在创建响应中出现一次，不得持久化到浏览器或日志。先写角色矩阵、跨工作区、项目边界和撤销立即生效测试。
```

### 23.6 M5 追加提示词

```text
只实现工作区 JSON 导出，不实现部署级数据库备份。复用现有任务状态模式。导出必须版本化、带 manifest 和 SHA-256，不得包含任何凭证或哈希。下载时重新鉴权，并测试伪造 job ID、workspace ID 和路径。
```

### 23.7 M6 追加提示词

```text
只实现部署级备份、恢复、验证和文档。所有破坏性操作只允许针对明确的 Compose 测试环境，执行前解析并验证目标。不得对开发者现有数据库执行恢复。任何真实恢复演练必须记录命令和校验结果。
```

### 23.8 M7 追加提示词

```text
只修复两套 CLI 的 local profile、认证、URL、响应 envelope 和现有记忆命令契约。不得新增 workspace/project 等命令。逐个移除已经修好的 xfail，并保证 Hosted profile 不回归。
```

### 23.9 M8 追加提示词

```text
本次只实现一个明确命令族：[填写命令族]。Python 和 Node 必须同时实现并通过 parity 测试。旧命令兼容性不得破坏。不要实现其他命令族，完成后停止。
```

### 23.10 M9 追加提示词

```text
只实现 integrations/ume-mcp。stdout 必须只包含 MCP 协议，日志写 stderr。工具必须使用 connector 最小 scope、有限输入、明确超时和结构化错误。先做离线测试，再做两个真实客户端 smoke；无真实环境时标记 NOT RUN。
```

### 23.11 M10 追加提示词

```text
只建立并实现 Dashboard Playwright 关键旅程。不得修改 CI workflow。使用稳定 data-testid、条件等待和独立测试数据，禁止固定 sleep。测试失败时修根因，不得放宽断言或增加不合理超时。
```

### 23.12 M11 追加提示词

```text
只执行安全、脱敏、性能和可靠性验证。不得编造性能数字。每项结果必须带环境、数据规模、命令和原始报告路径。发现安全漏洞时先添加失败测试并修复根因，不得只在单个路由加临时 guard。
```

### 23.13 M12 追加提示词

```text
只做发布验收和文档收口，不新增产品功能。逐条验证 PRD §11，状态只能是 PASS、FAIL、BLOCKED 或 NOT RUN。没有命令和证据的项目不得标 PASS。禁止修改 .github/workflows，禁止打开 PR。
```

## 24. 每个任务的证据要求

MiniMax 必须把以下证据保存在回复或指定报告文件中：

- 开始时和结束时的 `git status --short`。
- 相关测试第一次失败的摘要，以及修复后的结果。
- 完整检查的命令、退出码和通过/失败/跳过数量。
- migration revision 和 upgrade/downgrade 结果。
- API 示例必须来自真实测试或 OpenAPI，不得凭空编写。
- E2E 截图或 trace 的路径，不提交包含真实数据的大型产物。
- 性能测试的环境和原始输出路径。
- 受阻项的原始错误信息和复现命令。

## 25. 决策点：必须停下来询问

遇到以下情况 MiniMax 必须停止，不得自行决定：

1. 是否改变公开 API 或删除兼容命令。
2. 是否新增依赖、框架、数据库、队列或对象存储。
3. 附件/导出文件使用本地文件系统还是 S3 兼容存储。
4. 永久删除在备份中的清理周期。
5. 审计读取本身是否生成审计事件。
6. 是否实现用户邀请/管理员创建用户接口。
7. 是否把 SDK `chat()` 纳入 V1。
8. 是否修改 `.github/workflows/`。
9. 是否需要数据破坏、重置、删除 volume 或覆盖数据库。
10. 测试环境缺少真实第三方凭证且验收需要联网调用。

## 26. 功能完成矩阵

开发过程中维护以下矩阵；只有证据齐全才能勾选。

| 功能 | 实现 | 单测 | 集成测试 | 权限测试 | UI/E2E | 文档 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 工作区与成员 | 已有，复验 | 待复验 | 待复验 | 待复验 | 部分 | 部分 | 未完成 |
| 项目 | 已有，复验 | 待复验 | 待复验 | 待复验 | 部分 | 部分 | 未完成 |
| 对话与导入 | 已有，复验 | 待复验 | 待复验 | 待复验 | 部分 | 部分 | 未完成 |
| 记忆来源与版本 | 后端已有 | 待复验 | 待复验 | 待复验 | 未完成 | 部分 | 未完成 |
| 图谱 | 后端已有 | 待复验 | 待复验 | 待复验 | 未完成 | 部分 | 未完成 |
| 时间线 | 后端已有 | 待复验 | 待复验 | 待复验 | 未完成 | 部分 | 未完成 |
| 上下文组装 | 后端已有 | 待复验 | 待复验 | 待复验 | 未完成 | 部分 | 未完成 |
| 连接器 | 后端已有 | 待复验 | 待复验 | 待复验 | 未完成 | 部分 | 未完成 |
| 审计 | 写入已有 | 部分 | 未完成 | 未完成 | 未完成 | 未完成 | 未完成 |
| 工作区导出 | 未完成 | 未完成 | 未完成 | 未完成 | 未完成 | 未完成 | 未完成 |
| 备份恢复 | 未完成 | 不适用 | 未完成 | 未完成 | 不适用 | 未完成 | 未完成 |
| CLI Local | 未完成 | 部分 xfail | 未完成 | 未完成 | 不适用 | 部分 | 未完成 |
| CLI V1 命令 | 未完成 | 未完成 | 未完成 | 未完成 | 不适用 | 未完成 | 未完成 |
| 统一 MCP | 未完成 | 未完成 | 未完成 | 未完成 | 客户端 smoke 未完成 | 未完成 | 未完成 |
| Dashboard E2E | 未完成 | 不适用 | 未完成 | 覆盖在 E2E | 未完成 | 不适用 | 未完成 |

## 27. 最终完成定义

UME V1.0 只有在以下条件全部成立时才能宣称完成：

- PRD §11 每一项都有真实 PASS 证据，没有未解释的 FAIL/BLOCKED/NOT RUN。
- 所有公共接口具有类型、权限、错误、分页和文档。
- 所有跨工作区和伪造 ID 测试失败关闭。
- 导入、导出、记忆写入和恢复具有失败状态及可重试路径。
- CLI Python、CLI Node 和 MCP 对本地部署完成真实 smoke。
- Dashboard 核心旅程通过自动化 E2E。
- 空库迁移、基线升级、降级和再升级通过。
- 备份、恢复和恢复后 smoke 通过。
- 日志、审计、错误、遥测和导出中不存在明文凭证。
- 所有触及包的 lint、typecheck、test 和 build 实际运行。
- 文档命令在目标环境验证。
- 工作树没有秘密、临时文件、测试数据库、下载产物或无关改动。

未满足任何一项时，应报告“部分完成”并列出精确缺口，不得用“基本完成”“应该可用”或“理论通过”替代证据。
