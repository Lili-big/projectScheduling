# 任务清单：路面求解时限手动输入

**输入**：[规格](./spec.md)、[计划](./plan.md)、[研究](./research.md)、[数据模型](./data-model.md)、[接口契约](./contracts/solve-budget.md)、[验证指南](./quickstart.md)。

**状态**：用户已确认实施；7 项全部完成，相关测试、构建和临时页面验收通过。既有全仓快照差异按下方证据记录为非阻塞项。

## 用户故事 1：手动选择单次求解时间（P1）

**独立验收**：默认 15 秒；两类求解接受自定义预算；15 秒基准可按 30 秒继续优化窝工，业务基准和工期上限不变。

- [x] T001 [US1] 在 `04-demo/backend/tests/test_pavement_contracts.py`、`04-demo/backend/tests/test_pavement_api.py`、`04-demo/backend/tests/test_pavement_stream.py`、`04-demo/backend/tests/test_pavement_hybrid.py` 按现有职责补充预算字段校验与回退、15 秒基准加 30 秒独立预算、started/结果/截止时间一致性、cap/基准指纹保持、真实业务变更仍拒绝的最小用例；用测试替身证明预算透传，不要求每例耗满预算。
- [x] T002 [US1] 在 `04-demo/frontend/tests/pavementLiveSolve.test.mjs` 补充 15/30/60 秒请求构造、独立窝工预算、连接等待预算、无效值、旧调用方回退和原对象未被修改的行为断言；复用既有中断/异常保留方案用例，不重复同一测试。
- [x] T003 [US1] 在 `04-demo/backend/app/contracts/_models.py` 与 `04-demo/frontend/src/contracts/scheduler.ts` 同步可选 time_budget_seconds；在 `04-demo/backend/app/api/routers/scheduling.py`、`04-demo/backend/app/scheduling/application/pavement.py`、`04-demo/backend/app/scheduling/solver/strategies/pavement.py` 透传有效运行预算，只用于截止时间、started 和本轮元数据，保留原完整基准验证和省略字段时的旧行为。
- [x] T004 [US1] 在 `04-demo/frontend/src/app/workflows/solveWorkflow.ts` 实现可选运行预算传递与请求副本构造，窝工仅恢复基准原时限；在 `04-demo/frontend/src/api/_schedulerApi.ts` 发送独立预算并按有效预算设置连接等待，保持原业务 fingerprint 和流式事件校验。
- [x] T005 [US1] 在 `04-demo/frontend/src/app/Workspace.tsx` 的路面工具栏加入默认 15 的秒数输入与就地校验，两类按钮共享输入，计算中禁用编辑与提交；草稿不写入 scenario 或 dirty；仅改预算保留结果与窝工可用性，真实业务变更仍失效；使用现有布局样式。
- [x] T006 [US1] 使用既有 capture 脚本更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json` 与 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 中必要契约差异，核对新增可选字段及签名，不吸收无关 API 变化；演示镜像不支持路面的行为由 T001 现有用例继续覆盖。
- [x] T007 [US1] 按 `03-requirements/specs/075-pavement-solve-time-input/quickstart.md` 运行一批相关前后端测试、构建及契约检查；在临时页验收输入、按钮冻结、30 秒窝工预算和结果保留，在本 `tasks.md` 记录实际命令、退出码和未覆盖风险。原用户页不刷新，配置不保存。

## 依赖与执行顺序

T001、T002 定义验收；T003 → T004 → T005 接通功能；T006 在契约变更后执行；T007 在实现与快照完成后一次性验证。共 7 项，全部属于 US1；采用顺序执行，无并行代理任务。

## 一致性检查

已核对规格、计划、数据模型和接口契约，结果通过；未发现冲突、孤立任务、缺失依赖或覆盖缺口。

| 来源 | 实施或验收覆盖 |
| --- | --- |
| FR-001；US1 场景 1；SC-001 的默认/编辑 | T002、T005、T007 |
| FR-002；US1 场景 2；SC-001 的实际预算 | T001—T005、T007 |
| FR-003；US1 场景 3；SC-002 | T001、T002、T003、T004、T005、T007 |
| FR-004；US1 场景 4/5；SC-003 | T001、T002、T005、T007 |
| FR-005；US1 场景 6；SC-004 的结果/异常 | T001—T004、T007；复用既有预算与异常测试 |
| FR-006；旧调用方、无持久化；SC-004 | T001—T006、T007 |
| 计划：独立运行预算，原身份不变 | T003、T004；T001、T002 验证 |
| 计划：不覆盖原对象，配置与原页保护 | T002、T004、T005、T007 |
| 计划：共享契约/镜像保持 | T001、T003、T006、T007 |

## 确认边界

用户确认后进入 speckit-implement；不额外增加审查阶段。本清单不包含之前讨论的两阶段窝工算法。

## 设计阶段校验记录（2026-09-28）

- 本功能 7 份文档的相对链接和占位内容检查通过；上述需求到任务的一致性检查通过。
- `validate_repository.py` 退出 1：现有 requirements.txt 与架构依赖快照不一致。本次没有修改 requirements.txt 或架构快照，git diff 对两者为空。
- `validate_lifecycle_workspace.py` 退出 1：现有其他目录有 9 项工作包引用缺失，涉及客户验证材料与 json-task-viewer 输入/输出；无本功能目录违规。
- 上述全仓问题不属于本次变更，已记录且不扩展修复；不将其描述成全仓校验通过。尚未运行产品测试或修改产品源码。

## 实施与验收记录（2026-09-28）

### 实际修改

- T001—T002：先补充预算字段、回退、独立预算、截止时间和原对象保护测试；选定新增用例在实现前因缺少字段/参数/解析函数失败，随后实现并通过下述一批验证。
- T003：新增可选 `PavementIdleOptimizeRequest.time_budget_seconds`，默认回退原方案时限；路由、应用层、求解器透传本轮预算，仅作用于截止时间、启动事件和本轮元数据。完整基准校验、工期上限、目标和线程设置保持原实现。
- T004：前端在请求副本上设置时限；窝工仅恢复基准原始时限并独立携带新预算，连接等待按新预算加原有 30 秒余量。启动事件预算不匹配时按异常处理并保留方案。
- T005：路面工具栏新增默认 15 秒输入框；有限正数有效，错误就地提示；两种计算共用输入，运行时禁用编辑和重复提交。时限草稿不进入业务指纹或配置保存状态。
- T006：仅更新后端架构快照的新增可选字段。前端捕获器只记录公开类型名称，不记录字段/函数签名；本次无对应类型名称变化，故前端快照无需修改，避免吸收既有差异。
- T007：完成下面的测试、构建、契约差异核对及真实页面验收；临时页已关闭，用户原结果页未刷新，未保存配置。

### 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks` | 0 | 实施前提通过，按已确认清单执行 |
| `.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_stream.py 04-demo/backend/tests/test_pavement_hybrid.py -q` | 0 | 122 passed，6.51 秒 |
| `node --test 04-demo/frontend/tests/pavementLiveSolve.test.mjs` | 0 | 13 passed |
| `npm run build` | 0 | TypeScript/Vite 构建成功，仅既有 chunk 大小提示；生成 `index-xCsaPdqk.js` |
| `.venv/Scripts/python.exe 04-demo/backend/scripts/capture_architecture_baseline.py --check 04-demo/backend/tests/fixtures/architecture/backend-baseline.json` | 1 | 既有快照不一致，见下方归因 |
| `node 04-demo/frontend/scripts/captureArchitectureBaseline.mjs --check 04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` | 1 | 既有快照不一致，见下方归因；同一批后续命令的退出 0 不代表该检查通过 |
| `git diff --check` | 0 | 无差异格式错误；仅工作树换行规范提示 |

### 临时页面验收

- 新开临时页默认值为 15；输入 60、30 均保留，未截断到 15。空值、0、负数显示错误且禁用求解；恢复合法值后恢复可用。
- 现有合法配置的 19 段、95 道工序，按 15 秒普通求解得到 144 天可行方案；结果记录预算 15 秒、合计 15.08 秒。运行中输入框及两类按钮禁用。
- 将时限从 15 改成 60，再改为 30，结果仍保留且“优化窝工”可用。按 30 秒执行窝工优化，启动提示和结果预算均为 30 秒；建模 0.19 秒、优化 29.98 秒、合计 30.18 秒。
- 窝工从 150 降至 20 机组·天，合法改善 4 次；工期上限和当前工期均为 144 天，完成日仍为 2027-01-22；8 线程与内置 LNS 保持。页面明确尚未证明窝工最小。
- 有结果时清空输入，错误显示、计算禁用、结果仍保留；恢复 30 后可继续优化。保存配置按钮始终禁用，未修改资源、主数据或保存配置。
- 服务已按 runtime 标准脚本载入本次代码，健康检查正常，在线 OpenAPI 含新字段。仅重启已确认的原服务；新服务 PID 42912，保留运行。日志：`.local-data/logs/20260928-140628-183/`。
- 验收截图：`.local-data/logs/20260928-140154-solve-budget/budget-input-verified.png`。用户原标签页及其中既有结果保持原状，临时验收页已关闭。

### 非阻塞问题与覆盖边界

- 实施前后架构捕获文件保存于 `.local-data/logs/20260928-140154-solve-budget/` 的 `backend-before.json`、`backend-after.json`、`frontend-before.json`、`frontend-after.json`。
- 后端前后捕获差异仅为 `models/schemas/PavementIdleOptimizeRequest/properties/time_budget_seconds`；该字段已同步到快照。原快照与实施前捕获另有 46 项叶值/容器差异，涉及既有路由、路面工序字段和依赖摘要等，本次不吸收。
- 前端前后捕获差异仅为构建字节数；原快照与实施前捕获已有构建体积、样式行数、公开类型导出 3 项差异。本次字段和参数由 TypeScript 构建及预算行为测试验证，不扩大更新快照。
- 上述差异在实施前已经存在，不影响本次预算输入、透传和基准保护验收；保留全仓架构检查未通过的事实。设计阶段记录的依赖摘要和工作包引用问题亦未扩展修复。
- 15/30/60 秒预算透传及截止时间、旧调用方、真实业务变更拒绝、断线保留方案由相关自动测试验证。浏览器实际执行 15 秒普通求解和 30 秒窝工优化各一轮，未重复耗满 60 秒，也未人为断开用户服务。
- 时限是单次计算预算，收尾和通信可能使实际总耗时略超预算；时限不持久化，页面重新进入默认 15 秒。
