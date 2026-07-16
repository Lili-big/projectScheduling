# 架构迁移清单与批次记录

## 1. 实施起点

- 记录日期：2026-07-16
- 当前分支：`feature/scheduling-girder-integration`
- 上游：`origin/feature/scheduling-girder-integration`
- 实施前工作树：仅 `.specify/feature.json` 和 `specs/042-repo-architecture-modernization/` 属于本功能；无生产代码未提交改动。
- 受影响主路径：`backend/`、`frontend/`、`docs/`、`tools/`、`README.md`、`agent.md`、根配置与 042 规格目录。
- 明确不覆盖：`041` 的任务完成状态、用户本地 `.local-data/`、`.local.env`、根样例 Excel 内容、历史规格目录和未列入资产清单的交付件。

实施期间如出现新的用户改动，必须先在本表登记所有者和处理方式；无法安全避让时停止对应批次。

## 2. 固定基线

| 基线 | 位置 | 比较规则 |
| --- | --- | --- |
| 后端 API、schema、旧导入、依赖、固定场景 | `backend/tests/fixtures/architecture/backend-baseline.json` | 结构化 JSON 完全一致；明确允许的非业务字段除外 |
| 前端导出、40 个 API、热点规模、构建、npm 锁依赖 | `frontend/tests/fixtures/architecture/frontend-baseline.json` | 公开导出和依赖完全一致；规模和包体按阈值比较 |
| 仓库资产、引用、跟踪状态和哈希 | `repository-inventory.json` | 迁移前逐文件复核，二进制哈希必须一致 |
| `041` 状态 | `041-status-baseline.md` | 74 个完成、21 个未完成，不因本重构自动变化 |

## 3. 每批记录模板

每个批次完成后复制此模板填写，不得把多批验证合并成一次事后说明。

```text
批次：Batch N / <名称>
状态：planned | in_progress | passed | blocked | rolled_back
前置条件：
- 工作树冲突检查：
- 上一批门禁：
- 用户审批（如需要）：

迁移范围：
- 旧入口：
- 新所有权：
- 兼容 façade：

验证证据：
- 命令：
- 结果：
- 契约差异：
- 行为差异：
- 性能/包体差异：

回退：
- 回退文件：
- 回退步骤：
- 数据兼容注意事项：

阻断和遗留风险：
- 无，或列出编号、所有者和解除条件。
```

## 4. 批次计划与即时记录

| Batch | 范围 | 前置条件 | 必需验证 | 回退边界 | 状态/证据 |
| --- | --- | --- | --- | --- | --- |
| 0 | 基线、兼容测试、治理脚本 | 规格和检查表完成；工作树无生产改动 | 采集脚本可重复；45 路由、40 API；依赖无变化 | 只删除本批新增夹具/脚本，不影响运行 | `passed`；后端 10/10、前端 3/3、统一门禁通过 |
| 1 | 入口文档与架构地图 | Batch 0 通过 | 文档事实、链接、10 分钟定位 | 恢复入口文档；架构文档独立移除 | `passed`；定位 12/12、事实 4/4、文档门禁通过 |
| 2 | HTTP 启动与 routers | Batch 0 通过 | OpenAPI、真实 HTTP、静态与旧 endpoint 导入 | `app.main` 恢复为原装配 | `passed`；45 操作零差异，ASGI 12/12，既有专项 29/29 |
| 3 | 后端契约与领域服务 | Batch 2 通过 | schema/dump、旧导入、存储兼容 | 旧模块继续作为唯一实现 | `passed`；契约 9/9、façade 4/4、基线零差异 |
| 4 | 场景与求解器 | Batch 3 通过 | 固定行为、全量测试、性能 | façade 切回原实现 | `passed`；分域 13/13、原求解回归 174/174、基线零差异 |
| 5 | 前端契约、工作台与样式 | Batch 0 及后端入口通过 | Node、类型、构建、视觉旅程 | 聚合入口切回原实现/样式 | `passed`；Node 35/35、构建通过、五页截图哈希完全一致 |
| 6 | 运行部署和性能 | Batch 2–5 通过 | 单服务、Docker、Netlify、10% 性能/5% 包体 | 回退部署配置和脚本 | `passed_with_env_limit`；统一门禁通过，Docker CLI 未安装 |
| 7 | 仓库资产物理迁移 | 逐文件清单完成并取得用户第二次明确确认 | 引用、哈希、工具可运行、文档路径 | 每个文件单独按清单回原路径 | `passed_with_runtime_note`；140/140 迁移、哈希与跟踪状态通过 |

## 5. Batch 0 记录

- 状态：`passed`
- 工作树冲突：未发现生产代码未提交改动。
- 新增内容：后端/前端基线采集器、仓库资产清单器、固定 JSON 夹具和 041 状态基线。
- 首次采集：45 个 `/api` 路由、153 个 Pydantic 模型、40 个前端 API 函数。
- 依赖变化：无；`requirements.txt` 和三个 npm 锁文件只读取、未改写。
- 回退：移除本批新增脚本、夹具和治理文档即可；无业务数据写入。
- 阻断：Batch 7 保持等待二次确认；不影响 Batch 0–6。
- 验证：`pytest` 新增架构专项 10 passed；`node --test frontend/tests/architectureCompatibility.test.mjs` 3 passed；`npm.cmd run verify:architecture` 通过。

## 6. Batch 5 记录

- 状态：`passed`
- 迁移范围：前端契约/API 端口、工作台 workflow/controller、任务与结果 feature、计划管控公开边界和全局样式。
- 兼容入口：`src/App.tsx`、`types/scheduler.ts`、`api/schedulerApi.ts` 保持；旧 202 个类型导出和 40 个 API 函数无差异。
- 自动验证：后端 370 passed/1 skipped；前端 Node 35 passed；`tsc && vite build` 通过；主 JS 471.51 kB（gzip 136.80 kB），相对 470.62 kB 基线增加 0.19%，低于 5% 门禁。
- 样式验证：原 4,927 行按原顺序重组后逐行完全一致；聚合入口 12 行；产出 CSS 仍为 86.82 kB（gzip 16.59 kB）。
- 视觉验证：只读 `HEAD` 基线与重构版本使用同一数据快照、同一 1440×900 视口，任务、结果、架梁、计划管控、AI 多方案五页截图 SHA-256 全部一致；控制台 0 error/0 warning。
- 回退：`App.tsx` 可重新指向原工作台，API/类型可继续走兼容 façade，CSS 可按聚合顺序恢复成原单文件；没有数据迁移。
- 证据：`quickstart.md`、`visual-regression.md`。

## 7. Batch 6 记录

- 状态：`passed_with_env_limit`
- 前置条件：Batch 2–5 均通过；未新增或升级依赖；锁文件未变化。
- 迁移范围：单服务冒烟、Docker/Netlify 契约、样例双路径兼容、构建预算、性能门禁和统一验证命令。
- 验证：单服务 health/root/asset/SPA fallback 均为 200；性能专项 2 passed/64.42 秒；Docker 静态契约和样例路径 3 passed；前端部署契约 2 passed。
- 统一门禁：`npm.cmd run verify` 通过，后端 374 passed/2 skipped、前端 37 passed、JS 471.51 kB/CSS 86.82 kB、冻结契约/依赖/仓库/文档均通过。
- 环境限制：执行 `docker --version` 返回命令不存在，本机未做镜像构建或容器健康检查；Dockerfile 继续由静态契约保护，交付环境需补一次实机验证。
- 回退：删除新增验证脚本和测试、恢复 package scripts/Dockerfile/样例搜索即可；无数据迁移。
- 即时审计：Batch 0–6 均在执行时记录前置、验证、差异和回退；Batch 7 继续等待逐文件清单后的二次确认。

## 8. Batch 7 迁移记录

- 状态：`passed_with_runtime_note`；用户于 2026-07-16 明确确认“按更新后的 140 项资产迁移清单全部执行”。
- 机器可读逐文件清单：[`asset-migration-manifest.json`](./asset-migration-manifest.json)。
- 执行范围：140 个文件，其中 124 个原受 Git 跟踪的资产和 16 个根目录本地日志；90 个通过 `git mv` 保持跟踪，34 个移到本地产物区后取消跟踪，16 个日志仅做本地移动。
- 完整性证据：每项包含源路径、目标路径、分类、迁移动作、迁移前后跟踪状态、字节数、SHA-256、审批状态和逐文件回滚说明。
- 迁移后验：140 个源文件均不再存在、140 个目标文件均存在、全部迁移目标 SHA-256 与清单一致；90/34/16 三类跟踪状态正确；根目录日志从 16 个降为 0。
- 门禁证据：治理、默认样例、文档事实和桥梁导入专项 30 passed；PPT `typecheck + layout` 通过且 0 finding；参考 API `noEmit` 与未部署检查通过；文档链接/API 事实检查通过。

### 8.1 按目标分区汇总

| 目标分区 | 文件数 | 处理方式 | 主要内容 |
| --- | ---: | --- | --- |
| `docs/` | 25 | 保持 Git 跟踪 | 产品 11、工程算法 4、验证 3、调研 3、历史案例 4 |
| `examples/` | 5 | 保持 Git 跟踪 | 根桥梁导入 Excel 1、结果查看器/样例 4 |
| `tools/` | 56 | 保持 Git 跟踪 | PPT 辅助工具 48、交付构建器 6、Netlify 参考 API 2 |
| `deliverables/` | 4 | 保持 Git 跟踪并保留哈希 | 正式 XLSX 交付物 |
| `artifacts/` | 34 | 移动后取消 Git 跟踪，不删除本地文件 | 可再生成预览/检查结果 31、临时锁 2、本地运行时 1 |
| `.local-data/logs/legacy/` | 16 | 仅本地移动，始终不跟踪 | 根目录现有 stdout/stderr 日志，共 37,956 字节 |

### 8.2 关键迁移路径

| 当前路径 | 计划目标 | 说明 |
| --- | --- | --- |
| 根目录 3 份方案文档 | `docs/product/` | 收敛根目录，只保留入口、配置和主模块 |
| `docs/` 当前 PRD、算法、验证、调研和历史案例 | `docs/product/`、`docs/engineering/`、`docs/validation/`、`docs/research/`、`docs/archive/application-case/` | 按权威范围分区，迁移后同步所有当前引用 |
| `docs/` 中 4 个 JSON/HTML 查看器资产 | `examples/result-viewer/` | 作为可复现实例保留跟踪 |
| `ai-ppt-system/` | `tools/ai-ppt-system/` | 48 个源代码/配置继续跟踪；其 output 中 22 个产物移至 `artifacts/` 后取消跟踪 |
| `netlify/demo-functions/` | `tools/demo-api-mirror/` | 明确为参考镜像，不作为生产后端或部署函数 |
| `outputs/` 中构建/校验脚本 | `tools/delivery-builders/` | 6 个可复用脚本继续跟踪 |
| `outputs/` 中最终 XLSX | `deliverables/awards/2026/`、`deliverables/validation/lugu/` | 4 个正式交付物继续跟踪并校验 SHA-256 |
| `outputs/` 中预览、检查 NDJSON、临时锁 | `artifacts/lugu-validation/` | 移动后取消跟踪；保留用户本地副本 |
| `.netlify-cli-runtime/` 中已跟踪配置 | `artifacts/netlify-cli/` | 本地运行状态移出版本控制；不输出其内容 |
| 根目录 16 个 `*.log` | `.local-data/logs/legacy/` | 端口 8000/5173 当前无监听；确认后只移动、不删除、不改变 Git 跟踪 |
| 根目录 `渠溪河特大桥结构设计表.xlsx` | `examples/bridge-import/` | 最后执行；代码与 Docker 已准备新旧双路径兼容 |

### 8.3 审批与回滚边界

1. T122 审批门禁已经满足；T123–T129 只执行了清单内 140 项，没有扩大到未列出的本地文件。
2. 清单内正式交付物、样例和本地产物均保留；没有删除用户文件。
3. 保持跟踪的文件使用 `git mv`；计划取消跟踪的文件先移动到 `artifacts/`，再从 Git 索引移除，本地内容保留。
4. 每批迁移后复核 SHA-256、引用、工具可运行性和统一验证门禁；任一失败即按清单中的 `rollback` 逐文件恢复。
5. 若只批准部分范围，先更新清单中对应条目的审批状态和本节统计，再实施被批准项。
6. 新后台进程通过 `tools/local-runtime/start_logged_process.ps1` 写入 `.local-data/logs/<启动时间>/`；不再在根目录生成新日志。

### 8.4 工具复核与未列入清单的本地例外

- `tools/ai-ppt-system` 使用迁移前本地依赖缓存临时 junction 完成 `npm run verify`，TypeScript 和版式检查通过；junction 已移除，旧 `ai-ppt-system/node_modules` 缓存未移动、未删除。
- `tools/demo-api-mirror/verify.mjs` 通过 TypeScript `noEmit` 检查，并确认 `netlify.toml` 未配置 Functions。
- 泸古验证工作簿在 `.local-data/tmp/` 完成 8 个工作表构建、全表预览、公式错误扫描和独立重新导入；临时文件和正式交付物均可读取，错误扫描为 0。捆绑运行时在首次导出完成后的退出阶段返回 `0xC0000409`，但独立重新导入两份文件均以 0 退出，正式交付物未被覆盖。
- `outputs/lugu-validation-20260715/node_modules` junction、`ai-ppt-system/node_modules` 和根目录未跟踪 `泸古1标架梁工点导入模板.xlsx` 不在获批的 140 项清单内，因此保持原状。它们不受 Git 跟踪；后续如需移动或删除，必须另行确认。
