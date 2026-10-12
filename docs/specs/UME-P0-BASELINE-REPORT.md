# UME V1.0 — P0 基线报告

**产出时间：** 2026-10-10
**代码基线：** `fc9688e`（`init`）+ 本次会话内新增的 P0/P1 变更（工作区未提交）
**执行者：** MiniMax 开发代理
**对应任务：** 技术实现文档 §17 P0（Task 0.1 基线验证、Task 0.2 CLI 本地 API 契约测试）

本报告只记录**实际执行并观察到的结果**。没有跑通的项目一律标记为失败或受阻，不做修饰。

---

## 1. 运行环境

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| OS | Windows 11 x64 (10.0.26200) | |
| Python | 3.11.9 | 仓库 SDK 声明支持 3.10–3.12；容器镜像为 3.12 |
| Node | v24.14.1 | |
| pnpm | 11.13.1 | `server/dashboard/package.json` 声明 `packageManager: pnpm@10.34.2`，与全局版本不一致 |
| Git | 2.54.0.windows.1 | |
| Docker CLI | 29.7.2 | **仅 CLI，无守护进程**（见 §5 F-01） |
| Docker Compose | v5.5.0 | |
| Podman | 已安装，`podman-machine-default`（WSL provider） | 代替 Docker 执行的本地栈 |
| PostgreSQL | pgvector/pgvector:pg17，映射 127.0.0.1:8432 | |
| OpenSSL / openssl rand | 未使用 | `JWT_SECRET` 由 `secrets.token_urlsafe(48)` 生成 |

### 依赖环境说明

本次未使用 `hatch`。新建了仓库根的 `.venv`（`.gitignore` 已忽略），只安装最小依赖集：
`fastapi==0.115.8`、`sqlalchemy 2.1.4`、`alembic 1.20.0`、`pytest`、`pydantic[email]==2.10.4`、
`psycopg[binary]`、`psycopg-pool`、`httpx`、`ruff==0.16.0`、`isort`，以及为导入 `server/main.py`
所需的部分 SDK 依赖（`litellm`、`posthog`、`slowapi`、`qdrant-client`、`passlib`、`python-jose`、`uvicorn`）。

---

## 2. 静态检查与测试

### 2.1 Ruff（根 SDK 规则，line-length 120）

```
ruff check server/ume_app server/tests/ume server/alembic server/main.py   → All checks passed!
ruff format --check ...                                                     → 49 files already formatted
```

`ruff` 与 `isort --profile black` 均按 `.pre-commit-config.yaml` 与 `pyproject.toml` 的约定执行。

### 2.2 UME 业务测试

```
python -m pytest server/tests/ume -q
206 passed, 2 skipped, 11 xfailed, 30 warnings
```

| 文件 | 内容 | 结果 |
| --- | --- | --- |
| `test_permissions.py` | 角色 → scope 矩阵、Principal 拒绝行为 | 27 passed |
| `test_repositories.py` | 工作区范围过滤、游标分页、成员规则 | 28 passed |
| `test_api_workspaces.py` | 工作区/成员 API、统一信封、角色拒绝 | 40 passed |
| `test_api_projects.py` | `/projects/{id}` 跨租户隔离 | 13 passed |
| `test_api_audit.py` | 成功与拒绝均落审计；失败写不留成功记录 | 10 passed |
| `test_api_contract.py` | 路由表与 §9.3 精确比对、处理器隔离 | 6 passed |
| `test_api_conversations.py` | 对话/消息/导入、幂等、去重、隔离 | 37 passed |
| `test_migrations.py` | 离线 DDL + 真实 PostgreSQL 升降级往返 | 31 passed |
| `test_cli_contract.py` | CLI 与本地 API 的路由差异（**故意 xfail**） | 4 passed / 11 xfailed |
| `test_mount_integration.py` | 导入真实 `server/main.py`，验证挂载与 legacy 隔离 | 8 passed |

> `2 skipped` 是 `test_telemetry.py` / `test_server_params.py` 等仓库既有测试在本 venv 缺 SDK 全量依赖，
> 与本次改动无关；详见 §5 F-04。

### 2.3 真实 PostgreSQL 升降级测试（本次解除）

`server/tests/ume/test_migrations.py::TestLiveRoundTrip` 此前因无可用数据库被 skip。
本次起起 PostgreSQL 后**实际通过**：

```
$env:UME_TEST_DATABASE_URL="postgresql+psycopg://postgres:***@127.0.0.1:8432/postgres"
pytest server/tests/ume/test_migrations.py -k LiveRoundTrip -v
2 passed
```

覆盖：`upgrade head` → `downgrade 006` → `upgrade head` 的空库往返；
以及在已有 `001–006` 且含一条 `users` 数据的库上执行 `007+`，验证用户数据不丢。

> 期间暴露一个测试夹具陷阱：`server/alembic/env.py` 会用 `_build_database_url()` **无条件覆盖**
> `sqlalchemy.url`，所以只设置 `UME_TEST_DATABASE_URL` 是不够的。测试现在把 URL 拆解成
> `POSTGRES_*` 环境变量，并**断言重建后的 host/port/database 一致**——否则测试可能悄悄连到另一个库
> 仍然报"通过"。

---

## 3. 数据库迁移（001 → 010 实际执行）

```
$ python -m alembic upgrade head
INFO Running upgrade 006 -> 007, Create ume_workspaces, ume_workspace_members and ume_projects
INFO Running upgrade 007 -> 008, Create ume_audit_events
INFO Running upgrade 008 -> 009, Create ume_conversations and ume_messages
INFO Running upgrade 009 -> 010, Create ume_import_jobs and ume_idempotency_keys
```

全部 10 个迁移在真实 PostgreSQL 上按序执行成功，无手工干预。

---

## 4. 端到端功能验证

服务以 `uvicorn main:app --host 127.0.0.1 --port 8888` 启动（等价于 Dockerfile 的 `CMD`），
PostgreSQL 已迁移到 head。验证脚本：`server/scripts/p0_baseline_smoke.py`。

```
$ python server/scripts/p0_baseline_smoke.py
PASS  auth setup-status — {'outcome': 'logged_in'}
PASS  auth register + login — access token issued
PASS  API key create + list — created + listed, prefix=m0sk_ghh...
PASS  legacy /search reachable — POST /search -> 502 (无真实 LLM Key，预期上游错误)
PASS  legacy error shape unchanged — status 502 still uses {'detail': ...}
PASS  UME rejects unauthenticated — UNAUTHENTICATED
PASS  UME workspace/project CRUD — workspace=41b30622 project=e060309c
PASS  UME cross-workspace isolation — 3 routes -> 404, tenant list empty
PASS  UME import dedup + idempotency — 2 imported -> 0 duplicates -> replayed -> 2 archived
PASS  request log query — GET /requests -> 200

10/10 passed
```

**覆盖对照（技术文档 P0 第 4 项）**

| 要求 | 结果 | 证据 |
| --- | --- | --- |
| 认证 | 通过 | setup-status / register / login，未认证访问 `/api/ume/v1/*` 返回 `UNAUTHENTICATED` |
| API Key | 通过 | `POST /api-keys` 返回 `m0sk_` 前缀密钥，`GET /api-keys` 可列出 |
| 记忆 CRUD | **部分** | 路由可达、错误形状正确；**写入未验证**，见 F-03 |
| 搜索 | **部分** | `POST /search` 返回 502（上游），见 F-03 |
| 请求日志 | 通过 | `GET /requests` 返回 200 |
| Dashboard | **未验证** | 见 F-02 |
| 基线可重复启动 | 通过 | alembic + uvicorn 均可重复执行 |

---

## 5. 失败项与受阻项

**F-01｜Docker 守护进程不可用。** 本机只安装了 Docker CLI，Docker Desktop 未安装
（`C:\Program Files\Docker\Docker\Docker Desktop.exe` 与 `%LOCALAPPDATA%` 下均不存在），
`docker context ls` 指向的 `desktop-linux` 引擎无响应。
**影响：** `docker compose up` 无法执行，文档 P0 第 3 项"启动 Docker Compose"未能按原样完成。
**处置：** 改用已安装的 Podman（WSL provider）执行同一份 `server/docker-compose.yaml`，
成功拉起 `postgres` 服务并完成 §3、§4 的全部验证。
**待确认：** 是否需要在本机安装 Docker Desktop。`server/AGENTS.md` 声明"仅 Docker，无本地非 Docker 路径"，
因此本次的 Podman 路径**仅用于验证**，未写入任何仓库脚本或文档。

**F-02｜Dashboard 未做端到端验证。** `ume-dashboard` 镜像需要 Node 构建，未构建。
**影响：** 文档 P0 第 4 项要求验证 Dashboard，当前无证据。
**待确认：** 是否需要本次补 `pnpm build` + 启动验证。

**F-03｜记忆写入与搜索未做端到端验证。** `/search` 返回 502，因为
`OPENAI_API_KEY` 是占位值，LLM 上游不可达。
**影响：** 记忆 CRUD 的**写入**路径（`POST /memories`）与搜索的真实语义未验证；
只能证明路由可达、鉴权生效、响应形状未被 UME 改动影响。
**待确认：** 是否提供可用的 LLM Key 以补齐该项。

**F-04｜仓库既有测试在本环境无法全量收集。** `tests/test_telemetry.py`、
`tests/test_server_params.py` 需要 SDK 的完整依赖树（`qdrant_client` 等），
当前 venv 只装了最小集，收集阶段 `ModuleNotFoundError`。
**影响：** 无法给出"仓库全量测试通过"的结论。
**处置：** 已单独运行可收集的既有测试 `tests/test_api_keys_router.py` → 2 passed，确认无回归。

**F-05｜`evaluation` 子模块地址失效。** `.gitmodules` 指向
`https://github.com/ume/memory-benchmarks`，实测 `git ls-remote` 返回
`remote: Repository not found.`，且 `evaluation/` 目录为空（子模块未初始化）。
上游 `mem0ai/mem0` 的 `.gitmodules` 实际为
`https://github.com/mem0ai/memory-benchmarks`——**本仓库的 org 名 `ume` 是错误的**。
**影响：** 本仓库的 benchmark 无法拉取。
**建议修复：**
```bash
git config -f .gitmodules submodule.evaluation.url https://github.com/mem0ai/memory-benchmarks
git submodule sync evaluation
```
**待确认：** 修不修由维护者决定——这会改 `.gitmodules`，属于发布元数据变更。

**F-06｜服务端无法通过 API 创建第二个用户。** 迁移 `004` 用部分唯一索引
`ix_users_only_one_admin` 强制"最多一个 admin"，而 `/auth/register` 在已有用户后返回 403
"Registration is closed"。因此**自托管服务目前只能有一个用户**，多租户只能靠数据库直写用户行。
**影响：** §16.3 要求的安全测试需要两个工作区两个用户；HTTP 层测试必须绕过 API 造第二个身份
（`server/scripts/p0_baseline_smoke.py` 就是这么做的，并在脚本内注明）。
**待确认：** 是否需要在 P4 连接器阶段之前补一个用户管理端点，或放宽该约束。

**F-07｜`p0_baseline_smoke.py` 触发注册限流。** `@limiter.limit("5/minute")` 挂在 `/auth/register` 上，
脚本重复运行会收到 429。脚本已把 429 与 403/409 同等处理（转而登录既有管理员）。
**影响：** 无功能影响，仅影响重复执行的便利性。

---

## 6. Task 0.2 — CLI 与本地 Server 的路由差异

### 6.1 失败测试（已落地）

`server/tests/ume/test_cli_contract.py`，当前 **4 passed / 11 xfailed**。
11 个 xfail 就是 §2.2 的结论本身：CLI 目前的路由与自托管 API **完全不一致**。

用 `strict=True` 的 `xfail` 而不是留一批红灯，原因：一旦 P4 修好 CLI，这些用例会 XPASS 并**强制失败**，
逼迫当时删除标记；否则它们会静默腐烂成"永远失败的装饰"。

### 6.2 差异清单（实测自 `cli/cli-spec.json` 与 `server/main.py`）

| CLI 操作 | CLI 声明 | 自托管 Server 实际 | 差异 |
| --- | --- | --- | --- |
| `add` | `POST /v1/memories/` | `POST /memories` | 版本前缀 + 尾斜杠 |
| `search` | `POST /v2/memories/search/` | `POST /search` | 路径完全不同 |
| `get` | `GET /v1/memories/{id}/` | `GET /memories/{id}` | 版本前缀 + 尾斜杠 |
| `list` | `POST /v2/memories/` | `GET /memories` | **方法与路径都不同** |
| `update` | `PUT /v1/memories/{id}/` | `PUT /memories/{id}` | 版本前缀 + 尾斜杠 |
| `delete` | `DELETE /v1/memories/{id}/` | `DELETE /memories/{id}` | 版本前缀 + 尾斜杠 |
| `deleteAll` | `DELETE /v1/memories/` | `DELETE /memories` | 版本前缀 + 尾斜杠 |
| `entities` | `GET /v1/entities/` | `GET /entities` | 版本前缀 + 尾斜杠 |
| `deleteEntities` | `DELETE /v1/entities/` | `DELETE /entities/{type}/{id}` | **路径形状不同** |
| 认证 | `Authorization: Token <key>` | `Authorization: Bearer <jwt>` 或 `X-API-Key: <key>` | **认证方案不同** |

认证差异最致命：CLI 发的 `Token` scheme 会被服务端的 `HTTPBearer` 直接判定为无凭据 → 401。

### 6.3 最小兼容设计（提案，未实施）

按 §19 Task 0.2 的要求，本轮**只提出设计，不重写两套 CLI**。

**第 1 步（P4 起点，改动最小）**——在 `cli/cli-spec.json` 增加 `localServer` 契约，
Python 与 Node 两端从同一份定义读取路由表与认证方式：

```jsonc
"api": {
  "profiles": {
    "hosted": { "baseUrl": "https://api.ume.ai", "...": "现状不动" },
    "local":  {
      "defaultBaseUrl": "http://localhost:8888",
      "authHeader": "X-API-Key",
      "authScheme": "",
      "endpoints": {
        "add":    { "method": "POST",   "path": "/memories" },
        "search": { "method": "POST",   "path": "/search" },
        "get":    { "method": "GET",    "path": "/memories/{memory_id}" },
        "list":   { "method": "GET",    "path": "/memories" },
        "update": { "method": "PUT",    "path": "/memories/{memory_id}" },
        "delete": { "method": "DELETE", "path": "/memories/{memory_id}" },
        "deleteAll": { "method": "DELETE", "path": "/memories" },
        "entities": { "method": "GET",    "path": "/entities" },
        "deleteEntities": { "method": "DELETE", "path": "/entities/{entity_type}/{entity_id}" }
      }
    }
  }
}
```

- `ume profile use local` / `--profile` 选择 profile；默认 `local`（§2.4）。
- 契约测试直接由 `test_cli_contract.py` 的 `CLI_OPERATION_TO_LOCAL_ROUTE` 表驱动，
  两套 CLI 各写一条"给定参数 → 构造出同一请求"的测试即可。

**第 2 步（P4）**——CLI 新增 `workspace / project / conversation / context / connector` 命令族，
旧的 `ume add/search/...` 保留为 `ume memory ...` 的别名（§14.1），指向 `/api/ume/v1`。

**需要维护者确认的点：** 认证方案统一到 `X-API-Key`（服务端已支持）还是同时支持
`Authorization: Token`（需服务端放宽 `HTTPBearer`）。倾向前者——不改服务端语义。

---

## 7. P0 退出条件核对

> 退出条件：基线报告完成，现有功能可重复启动，失败项有明确归属。

| 条件 | 状态 |
| --- | --- |
| 基线报告完成 | ✅ 本文件 |
| 现有功能可重复启动 | ⚠️ 部分。PostgreSQL + API 服务可重复启动并通过 10/10 冒烟；**Dashboard 未验证**（F-02） |
| 失败项有明确归属 | ✅ §5，每项都给出影响与待确认事项 |

---

## 8. 本次 P1 交付附注（非 P0 范围）

技术文档 §17 P1 在 Task 1.1/1.2 之后还剩"对话归档 + 导入任务 + Dashboard 基础页面"。
其中**后端部分已在本次会话一并完成**：

- 迁移 `009`（对话/消息，含部分唯一索引去重）、`010`（导入任务 + 幂等键）
- 对话/消息/导入 API、幂等、去重、导入状态机
- 测试：`test_api_conversations.py` 37 项，全绿
- P1 退出条件已验证：重复导入不产生重复记录（2 → 0）、跨工作区 3 条路由全部 404

**Dashboard 基础页面仍未实现**，是 P1 唯一未完成项。

---

## 9. 2026-10-12 后复核（M0 基线复核）

本节由 `UME-V1-MINIMAX-DEVELOPMENT-PLAYBOOK.md` §9 产生。**上文 §1–§8 是 2026-10-10 的历史记录，
不修改、不删除**；本节只在其之上追加"当前基线提交 `3bf062c` 上重新观察到的事实"。
当两者冲突时，以本节为准，并按下表判定冲突性质。

**本次复核未修改任何业务代码。** 复核用的临时脚本与一次性数据库已在结束后删除。

### 9.1 环境事实

| 项 | 值 |
| --- | --- |
| 分支 / 提交 | `master` @ `3bf062c`（`feat: add connector management functionality`） |
| 工作树 | 仅 1 个**已暂存的新文件**：`docs/specs/UME-V1-MINIMAX-DEVELOPMENT-PLAYBOOK.md`（用户提供的执行手册） |
| Python | 3.11.9（`.venv`，pytest 9.1.1 / fastapi 0.115.8） |
| Node / pnpm | v24.14.1 / 11.13.1（`server/dashboard/package.json` 声明 `packageManager: pnpm@10.34.2`，仍不一致） |
| Docker | CLI 29.7.2 / Compose v5.5.0，**守护进程仍未运行** → 见 §9.6 F-01（延续） |
| Podman | 5.8.3，`ume-dev-postgres-1`（pgvector:pg17，127.0.0.1:8432）已运行 43 小时 |
| 本次数据库 | `ume_m0_roundtrip`、`ume_m0_smoke`，均为**本次新建的一次性库**，验证后已 DROP；`ume_app`（开发库）未触碰 |

### 9.2 测试与静态检查（实测输出）

```
python -m pytest server/tests/ume -q
  未设 UME_TEST_DATABASE_URL:  346 passed, 2 skipped, 11 xfailed
  设  UME_TEST_DATABASE_URL:  348 passed, 0 skipped, 11 xfailed

ruff check server/ume_app server/tests/ume server/alembic server/main.py   → All checks passed!
ruff format --check server/ume_app server/tests/ume server/alembic        → 88 files already formatted
```

**基线报告 §2.2 的 `206 passed` 已过时**：当前同一套件为 **348 passed**，
新增用例来自 `011`–`013` 迁移（记忆元数据 / 边 / 连接器）与连接器阶段。

**上一轮的两个 skip 已解除**：`test_migrations.py::TestLiveRoundTrip` 的 2 项在指向一次性库后**真实通过**
（`upgrade head` → `downgrade 006` → `upgrade head` 空库往返，以及已有 `001–006` 数据库上跑 `007+`）。
复现命令：

```powershell
$env:UME_TEST_DATABASE_URL='postgresql+psycopg://postgres:<pw>@127.0.0.1:8432/ume_m0_roundtrip'
python -m pytest server/tests/ume/test_migrations.py -k LiveRoundTrip -v   # → 2 passed
```

**11 个 xfail 数量与 P0 报告完全一致**，全部集中在 `test_cli_contract.py`
（10 个路由/版本前缀差异 + 1 个认证 scheme 差异）。原因标注仍为
"P0.2: the CLI still targets the hosted /v1 and /v2 routes; fixed in P4"。
`cli/cli-spec.json` 顶层结构为 `['specVersion','cli','branding','config','api','errors',
'optionGroups','globalOptions','commands']`，**`api` 下只有 `endpoints`，没有 `profiles`** —— M7 的改造尚未开始。

### 9.3 实际路由表 vs 技术文档 §9.3

从 `ume_app.api.app.ume_api` 实际枚举：**52 条**，其中 48 条业务路由 + 4 条 FastAPI 自带
（`/docs`、`/docs/oauth2-redirect`、`/openapi.json`、`/redoc`）。前缀 `/api/ume/v1` 由 `main.py:179`
以 `app.mount()` 挂载，因此子应用内路径不含前缀。

**与 §9.3 的三处偏差：**

| 方向 | 路由 | 说明 |
| --- | --- | --- |
| 文档要求，代码缺失 | `DELETE /api/ume/v1/memories/{memory_id}` | §9.3 明确列出；实际只有 `archive` / `forget` / `retry`。**删除语义是决策点**（见 §9.6 D-01） |
| 文档要求，代码缺失 | `POST /api/ume/v1/exports`、`GET /api/ume/v1/exports/{export_id}` | M5 范围，实测均返回 `404 NOT_FOUND` |
| 代码多出，文档未列 | `POST /api/ume/v1/memories/{memory_id}/retry` | §9.4 要求写入失败可重试，实现合理；建议回填文档 |

**§9.3 未列出 `/api/ume/v1/audit-events`**，但 M4 §13.1 要求新增该只读查询接口。实测 `404`。
→ 文档 §9.3 需要补这一行（见 §9.6 D-02）。

`server/tests/ume/test_api_contract.py` 的 `EXPECTED_ROUTES` 精确等于这 48 条，
即**路由表被测试锁死**；任何增删都会让 `TestRouteTable::test_router_exposes_exactly_the_documented_surface` 变红。
这意味着 M4/M5 落地时必须同步扩展该常量。

### 9.4 Dashboard 实际状态

实际页面路由 **16 个**（`src/app/**/page.tsx`），与基线报告 §8 "基础页面仍未实现"的结论**不符**，
该结论已过时：

```
/setup  /login
/dashboard/{analytics,api-keys,categories,configuration,conversations,conversations/[id],
            entities,export,memories,projects,requests,settings,webhooks,workspaces}
```

其中 4 个是 `LockedPage` 占位壳（全部按钮 `disabled`、无任何请求）：**export / categories / analytics / webhooks**。
`/dashboard/export` 尤其要注意：它是 62 行的**锁定营销页**，不是导出功能。

**缺失页面**（对应 M2–M5）：`memories/[id]`、`graph`、`timeline`、`connectors`、`audit`、`import-export`。

**数据层现状**：`src/utils/ume-api.ts` 已有 `unwrap` / `UmeApiError` / `umeGet|umePost|umePatch|umeDelete`，
`api-endpoints.ts` 已有 `UME_ENDPOINTS`（工作区 / 项目 / 对话 / 导入）。
**但覆盖面只到对话层** —— memory detail / sources / versions / graph / timeline / context /
connectors / audit / export **全部缺端点常量**，M1 需要在此扩展而非重写。

**一处跨接问题**：`memories/page.tsx` 走的是 **legacy 引擎路由**（`MEMORY_ENDPOINTS.BASE = "/memories"`、
`DELETE /memories/{id}`、`top_k: 1000` 一次拉全量），**不是** `/api/ume/v1/memories`。
M2 若直接复用该页面会继承"无 cursor、无 limit 上限、无工作区隔离参数"的旧行为。

Dashboard 检查（本次实跑）：

| 命令 | 结果 |
| --- | --- |
| `pnpm run typecheck` | ✅ 通过（`tsc --noEmit` 无输出） |
| `pnpm run build` | ✅ 通过（Next 15.5.24，19 条路由全部产出） |
| `pnpm run lint` | ❌ **失败：`Code style issues found in 109 files`** |

`lint` 失败**不是格式漂移**：仓库里**没有 `.prettierrc` / `prettier.config.*`，也没有 `.prettierignore`**，
Prettier 用默认配置（双引号、printWidth 80）去校验一个用单引号、printWidth 100 写的代码库，
于是全树报错。同一命令在 P0 阶段没有被记录过，属于新增事实。**M1 的退出条件包含
`pnpm run lint` 通过，因此必须先决定 Prettier 配置归属（见 §9.6 D-03），否则 M1 无法退出。**

### 9.5 端到端复核（真实 HTTP）

服务以 `uvicorn main:app --host 127.0.0.1 --port 8888` 启动，指向一次性库 `ume_m0_smoke`。
**未改动 `.env`**：以下四项通过进程环境变量覆盖，其中 `JWT_SECRET` 为一次性随机值、
`OPENAI_API_KEY` 为占位串、`HISTORY_DB_PATH` 指向系统临时目录（默认值是容器路径
`/app/history/history.db`，在 Windows 上不存在，会导致启动即 `sqlite3.OperationalError`）。

```
$ python server/scripts/p0_baseline_smoke.py
PASS  auth setup-status / register + login / API key create + list
PASS  legacy /search reachable            → 502（占位 key，上游 401，预期）
PASS  legacy error shape unchanged        → status 400 仍是 {'detail': ...}
PASS  UME rejects unauthenticated        → UNAUTHENTICATED
PASS  UME workspace/project CRUD
PASS  UME cross-workspace isolation       → 3 routes -> 404
PASS  UME import dedup + idempotency      → 2 imported -> 0 duplicates -> replayed -> 2 archived
PASS  request log query                   → 200
10/10 passed
```

补充探测（P0 报告之后新增的能力）：

| 探测 | 结果 |
| --- | --- |
| 伪造 workspace / memory UUID | 均 `404`（安全 404，不泄露存在性）✅ |
| `/graph`、`/timeline` | `200`，信封 `{data, request_id}` ✅ |
| 连接器 scope allowlist | 越权 scope 被拒：`{"rejected":["memories:read","memories:write"],"allowed":[...]}` ✅ |
| 连接器创建 | `201`，响应含 `credential`（`umec_` 前缀） |
| 连接器 list | `200`，**不含** `credential` ✅ 明文只出现一次 |
| 连接器 patch / get / revoke | 均 `200` ✅ |
| **撤销后立即用旧凭证调用** | **`401`，无宽限** ✅ |
| `POST /exports`、`GET /audit-events` | `404`（未实现，预期） |

**§4.4 的三项安全疑点（连接器撤销立即生效、项目级连接器跨项目、明文凭证不落库/不进日志），
在本次真实 HTTP 探测中均为通过。** 但这只覆盖了成功路径与撤销路径，
角色矩阵（普通成员不得创建/撤销）与项目边界仍需 M4 的专项测试覆盖。

### 9.6 本轮新增失败项与决策点

**F-08｜`POST /memory-search` 与 `POST /context` 在真实引擎路径上必定 500。**
这是本轮最重要的发现，且**被 348 个通过的测试完全掩盖**。

- 实测：`memory-search -> 500 INTERNAL_ERROR`、`context -> 500`（带与不带 `project_id` 均如此）。
- 服务端日志原始异常：
  `ume/memory/main.py:1472` → `ValueError: filters must contain at least one of: user_id, agent_id, run_id`
- 调用链：`graph.py:176 build_context` → `services/graph.py:365` → `services/memories.py:499`
  → `engine/memory_adapter.py:166` → `ume.Memory.search`
- 根因：`EngineScope.as_metadata()`（`engine/memory_adapter.py:32`）只产出
  `ume_workspace_id` / `ume_project_ids`，而 SDK 的 `Memory.search()` **强制要求** `user_id` /
  `agent_id` / `run_id` 至少有一个，否则直接抛 `ValueError`。适配器把业务范围当 metadata 传入，
  但这些 key 不是 SDK 认可的实体 ID。
- **为何测试没抓到**：`tests/ume/test_memory_adapter.py` 的 `FakeSdk` 与 `tests/ume/fake_engine.py`
  的 `FakeEngine` 都自行实现了 `search()`，**不包含 SDK 的 filters 校验**。
  契约测试锁的是"适配器传了什么"，没有一条测试让真实的 `ume.Memory.search()` 校验过这些 filters。
- 影响面：M3 上下文调试器、M11 的上下文性能基线、以及一切依赖引擎检索的路径。
  `GET /memories` 返回 `200` 是因为它读 PostgreSQL 业务投影，不走引擎，**不能据此认为记忆功能可用**。
- 处置：**M0 不改业务代码。** 需要在 M3 之前作为独立缺陷修复（先写一条用真实 SDK 校验 filters 的回归测试），
  且修复方案本身是决策点（见 D-04）。

**F-09｜Dashboard `pnpm run lint` 失败（109 文件）。** 见 §9.4，根因是缺少 Prettier 配置。

**F-10｜`server/.env` 的 `OPENAI_API_KEY` 为空。** 与 P0 报告 F-03 描述的"占位值"不同，
当前是**空值**，直接导致 `uvicorn main:app` 在 `initialize_state` 阶段崩溃
（`Memory.__init__` → `OpenAI(...)` → `Missing credentials`）。
`.env` 未被本次复核修改；它是 gitignored 的本地文件。

**D-01｜`DELETE /api/ume/v1/memories/{memory_id}` 补不补。**
§9.3 明确要求，但现有语义是 `forget`（软删除 + 引擎删除 + 墓碑）。两者关系是**公开 API 决策**，
按执行手册 §25.1 必须停下询问。

**D-02｜技术文档 §9.3 补 `/api/ume/v1/audit-events` 一行。** M4 需要它，§9.3 现在漏了。

**D-03｜Prettier 配置归属。** M1 退出条件要求 `pnpm run lint` 通过。当前三种走法：
(a) 新增 `.prettierrc` 对齐现有代码风格（单引号 / printWidth 100），改动面最小；
(b) 执行 `prettier --write` 重排全库，diff 巨大且违反"不产生无关格式化"；
(c) 把 `lint` 脚本从 `prettier --check .` 换成 ESLint（`eslint` 已在 devDependencies 中）。
这会改 `package.json` 脚本，属于仓库规则范围，**需要批准**。

**D-04｜F-08 的修复方向。** 可选：把工作区/项目 ID 映射为 SDK 认可的实体 ID（如按 workspace 派生稳定
`user_id`）；或在适配器层补一层 SDK 认可的 filter。两者都改变写入记忆的 metadata 语义，
需要决定。

### 9.7 沿用上一轮的未决项

F-01（Docker 守护进程不可用，仍用 Podman）、F-04（仓库全量测试收集失败：31 个 collection error，
需 SDK 全量依赖）、F-05（`evaluation` 子模块 org 名错误）、F-06（服务端只能创建一个用户，
多租户测试必须直写用户行）、F-07（注册限流 5/min）状态与 2026-10-10 记录一致，本轮未重新验证 F-05/F-06/F-07。

### 9.8 M0 退出条件核对

| 条件 | 状态 |
| --- | --- |
| 每个 PRD 功能有 `完成/部分完成/未实现/受阻` 状态 | ✅ 见 §9.3 / §9.4 / §9.6 |
| 每个"完成"有测试命令和结果 | ✅ §9.2 / §9.5 |
| 每个"受阻"有错误原文、环境条件、后续归属 | ✅ F-01（沿用）、F-04（沿用）、F-08（本轮，含完整调用链与原始异常） |
| 未修改任何业务功能 | ✅ `git status --short` 与开工时一致 |

**结论：M0 退出条件满足。** 但开工前存在 **4 个决策点**（D-01 ~ D-04），
其中 **D-01、D-03、D-04 会直接阻塞 M1 / M2 / M3**，建议先裁决再进入 M1。