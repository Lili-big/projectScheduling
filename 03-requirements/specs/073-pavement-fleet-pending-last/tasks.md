# 任务清单：待移交段按单套机组后置

**日期**：2026-09-28  
**状态**：8/8，用户确认后已实施，核心验收通过；范围外校验差异见完成记录。  
**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[契约](./contracts/pending-policy.md)、[验证指南](./quickstart.md)。

## 用户故事 1：机组分别后置（3 项）

- [x] T001 [US1] 在 `04-demo/backend/tests/test_pavement_solver.py` 与 `04-demo/backend/tests/test_pavement_hybrid.py` 用合成双机组样例替代旧整体后置断言：R1 正常水稳 04-20、转场 04-21、允许待移交碎石 04-22，R2 正常沥青 04-28；固定 B 开工证明 CP-SAT 可行，检查初解和数值校验。覆盖同机组养生空档禁止插入、同类型两实例独立、零正常任务、全部/无待移交、真实跨机组前置、同机组固定顺序冲突和无主机组兼容任务。编写前已从旧全局门槛证明当前行为缺失，不重复跑旧测试作为证据。
- [x] T002 [US1] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 删除全局 normal_finish 约束和对应 hint；在 `04-demo/backend/app/scheduling/solver/constraints/pavement.py` 保留并明确已有逐资源路径 pending → normal 禁止规则。保留原最早施工完成目标、互斥、相邻转场及全部真实前置/日期约束，不新增两两排序模型。（依赖 T001）
- [x] T003 [US1] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py` 取消初解的全局正常完工时间下限，依实际机组路径判断正常/待移交阶段；数值校验拒绝同机组逆序、接受不同机组交错。正常优先构造遇到真实前置阻挡时不误判业务无解，保留合法候选尝试与 CP-SAT 兜底。（依赖 T002）

## 用户故事 2：规则标识与显示一致（3 项）

- [x] T004 [US2] 在 `04-demo/backend/tests/test_pavement_contracts.py`、`test_pavement_generation.py`、`test_pavement_api.py`、`test_pavement_stream.py`（均相对 `04-demo/backend/tests/`）以及 `04-demo/frontend/tests/pavementResults.test.mjs`、`pavementTaskPreview.test.mjs`、`pavementLiveSolve.test.mjs`（后两项相对 `04-demo/frontend/tests/`）覆盖新枚举生成/序列化、旧输入重新生成诊断、新旧结果说明、流式初解和最终快照一致、失败/中断无假日期。旧值保留历史读取用例。（依赖 T003）
- [x] T005 [US2] 在 `04-demo/backend/app/contracts/pavement.py` 扩展 pending_policy 为 `per_fleet_last`、历史 `strict_last` 或缺省；在 `04-demo/backend/app/scheduling/generation/pavement.py` 和 `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 生成新标识及按机组文案。旧标识求解输入以 `MODEL_INVALID` / `PAVEMENT_INPUT_OUTDATED` 提示重新生成；无范围元数据直接输入按任务实际状态生成当前标识，保留原计数、缺项、引用诊断及镜像不支持行为。（依赖 T004）
- [x] T006 [US2] 在 `04-demo/frontend/src/contracts/pavement.ts` 同步枚举；在 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx` 区分新旧规则说明，识别待移交清单并保留日期/原因/空态/中断表现；不重解释旧日期、不自动替换当前页面方案。（依赖 T005）

## 闭环验证（2 项）

- [x] T007 审阅共享枚举变更后，使用 `04-demo/backend/scripts/capture_architecture_baseline.py` 与 `04-demo/frontend/scripts/captureArchitectureBaseline.mjs` 仅按实际契约变化更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`；不覆盖无关既有变化。核对 `04-demo/tools/demo-api-mirror/api.mts` 仍明确拒绝路面请求，无需新增镜像实现。（依赖 T006）
- [x] T008 按 `03-requirements/specs/073-pavement-fleet-pending-last/quickstart.md` 执行一次相关 pytest、前端测试、构建、架构/仓库/文档校验批次；核对主数据与持久配置未修改，并将命令、退出结果、核心样例和未覆盖风险记入本 `tasks.md`，更新 `03-requirements/specs/README.md` 状态。若发现失败，按根因修复并只重跑受影响检查，不启动用户页面求解、不保存替代当前方案。（依赖 T007）

## 依赖与执行方式

顺序：T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008。共 8 项：US1 3 项、US2 3 项、闭环 2 项。多个任务共用 solver/测试文件，采用顺序实施，不分派独立代理。验证批次中无依赖的命令可同时执行。

## 一致性核对

2026-09-28 完成一次规格、计划、契约、任务交叉核对：

| 来源 | 覆盖任务或证据 |
| --- | --- |
| FR-001、US1 场景 1/2/3、SC-001/002 | T001、T002、T003：跨机组可交错，单机组不可逆序 |
| FR-002、US1 场景 4 | T001、T003、T004、T005：初解/CP-SAT/校验/流式一致 |
| FR-003、全部边界和冲突场景 | T001、T002、T003：前置/养生/日期/资源规则不变 |
| FR-004、原目标不变 | T002、T008：仍最小化全范围施工完成 |
| FR-005、US2 场景 3、SC-003 | T004、T005、T006、T007：新旧标识和输入失效策略 |
| FR-006、US2 场景 1 | T004、T005、T006：各入口文案及日期计算一致 |
| FR-007、US2 场景 2、SC-004 | T006、T008：只读历史/配置对比，无主数据变更 |
| FR-008、US2 场景 4 | T001、T004、T006、T008：诊断、未知、失败、中断、空态 |
| plan 决策 1/2/3/4 | T001、T002、T003 |
| plan 决策 5/6，data-model 与 contracts | T004、T005、T006、T007 |
| API 镜像能力边界 | 已读 api.mts 的 422 拒绝分支，T007 核对 |
| agent 上下文脚本 | 仓库文件名搜索未发现；不新造脚本、不改项目事实文件 |

结论：无覆盖缺口、无关键口径冲突、无范围外实现任务；算法/契约验证齐全，依赖明确。实际机组无正常分配任务不设门槛；不能通过候选资源池把其他实例的任务算成本机组任务。不承诺真实项目固定缩短 7 天。

## 实施门禁

用户于本对话明确回复“确认执行”，已满足根 `AGENTS.md` 的“用户确认 → speckit-implement”门禁。本清单按已确认的一致性结论实施完成。

## 规划产物校验记录

2026-09-28，新建资产后执行一次校验批次：

- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_docs.py`：退出 0，文档链接及 API 事实检查通过。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py`：退出 1，`requirements.txt changed without architecture dependency approval`；本次未修改依赖文件或审批清单，属于范围外阻塞，不伪称全库校验通过。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py --json`：退出 1，9 个 `missing-workpackage-reference`，位于既有客户验证成果和 standalone/json-task-viewer 引用；未指向本功能目录。本次不修改或清理这些资产。
- 未运行算法/构建验收，也未改源码或主数据；这些将在清单获确认后的实施阶段执行。

## 实施完成记录

2026-09-28，按确认清单顺序实施，未分派代理，未改依赖、主数据、机组配置或用户保存的方案。

### 实际修改与核心证据

- T001–T003：CP-SAT 删除全局正常段完工门槛，保留每套实际机组路径禁止 pending → normal；三个启发式初解策略及候选校验改为同一口径。真实跨机组前置仍被遵守，初解不可构造时保留 CP-SAT 兜底。
- 合成样例从 2027-04-20 起排：R1 正常水稳 1 天，04-21 转场，待移交碎石可在 04-22 开工；R2 正常沥青仍须养生后于 04-28 开工。三个初解策略均得到 9 天工期；固定待移交任务在 04-22 的 CP-SAT 样例可行。此证据仅证明跨机组整体等待已解除，不承诺用户真实项目固定缩短 7 天。
- 同机组养生空档不可插入待移交后再返回正常任务；同类型多套机组独立判断；无正常任务分配的机组无额外门槛。全部/无待移交、固定顺序冲突、真实跨机组前置、兼容无主机组任务均有测试覆盖。
- T004–T006：新生成输入、流式初解与最终结果使用 `per_fleet_last`；历史 `strict_last` 可读，历史结果保留原口径说明。旧输入重算返回 `PAVEMENT_INPUT_OUTDATED` 并提示重新生成；直接求解结果为 `MODEL_INVALID`，API 沿用预校验 HTTP 422。任务预览和结果说明同步为按机组后置，保留失败/中断/空态。
- T007：后端架构快照仅更新 16 处 `PavementHandoverScope.pending_policy`，由旧常量扩展为新旧枚举；程序核对其余内容完全保留。前端快照不捕获此枚举，没有相关结构变化，故未覆盖既有差异。Demo API 镜像仍以 HTTP 422 / `PAVEMENT_FEATURE_NOT_SUPPORTED` 明确拒绝路面求解。

### 验证命令与退出结果

命令均在仓库根目录执行，使用现有虚拟环境及依赖。

| 命令 | 结果 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_stream.py -q` | 初次退出 1：140 通过、4 个新增样例失败；原因为重复执行约束及测试前置缺少必填 source_rule_id。修正测试构造，未放宽业务断言。 |
| `.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_solver.py::test_pending_fleet_does_not_wait_for_another_fleets_normal_asphalt 04-demo/backend/tests/test_pavement_hybrid.py::test_cross_fleet_real_dependency_can_precede_a_normal_task -q` | 退出 0：4 通过；原批次全部 144 个用例均已通过，不重复运行已通过用例。 |
| `node --test 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementTaskPreview.test.mjs 04-demo/frontend/tests/pavementLiveSolve.test.mjs` | 退出 0：21 通过。 |
| `npm run build` | 退出 0：TypeScript 与 Vite 构建通过；保留大于 500 kB 的常规产物体积提示。 |
| `.venv/Scripts/python.exe 04-demo/backend/scripts/capture_architecture_baseline.py --check 04-demo/backend/tests/fixtures/architecture/backend-baseline.json` | 退出 1：剩余 46 处工作树既有差异，无 pending_policy 差异，分类见下。 |
| `node 04-demo/frontend/scripts/captureArchitectureBaseline.mjs --check 04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` | 退出 1：3 处导出/样式行数/当前构建体积差异，不涉及本次枚举快照。 |
| `.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py` | 退出 1：既有 requirements.txt 缺少架构依赖审批；本次未改依赖。 |
| `.venv/Scripts/python.exe 00-governance/repository-tools/validate_docs.py` | 退出 0：14 个文档的链接及 API 事实检查通过。 |

后端剩余差异为 `apply_unified_target_achievement` 导入导出、requirements 哈希、`PavementTaskContext.process_id`、`Resource.compatible_process_ids` 以及既有 `task-view-display-map` 路由。前端差异为 `MinimumResourceVerification` / `UnifiedSolveMetadata` 导出、根样式行数、当前构建字节数。均未通过刷新快照吞并。上述检查不能视为全库通过，但本次核心验收由针对性算法、契约、流式、UI 测试与构建独立证明，不阻塞本规则交付。规划阶段发现的 9 个生命周期引用问题亦未扩修或重复检查。

候选基线、修改前基线、差异列表、16 处选择性更新证据和本轮校验日志保存在 `.local-data/logs/20260928-012240-fleet-pending-last/`，属于本地运行证据，不纳入正式资产。

### 本地服务与状态保护

- 已核实旧服务 PID 36156 与启动器 18048 的命令和归属，仅重载本项目 8000 后端；使用统一 `start_logged_process.ps1` 启动，启动器 PID 29208，服务 PID 41272，日志 `.local-data/logs/20260928-012629-863/`。
- 只读检查 `/api/health` 为 `ok`，`/openapi.json` 已包含 `per_fleet_last`；根页面提供新构建 `index-Dj7to9-w.js`。未在用户浏览器发起求解、刷新页面或替换当前结果。
- 启动前后 SHA-256 均保持一致：`project-master.db` 为 `6E224DE570974B9BD17B58F81FBD7D5FE12B0DF73A7D4A65F1540B232821FE9B`；`scheduler-config.json` 为 `49CDAD9778A48EFDD6FAAD0B3D2EB29E3298FCA1DD85202AA93D62CA94F0494F`；`plan-control-store.json` 为 `18941FC0E540FF7784A77195348B49AAB2B60DFBB211470BFAD8A5BF62A30B0C`。
- 使用新规则需刷新加载新界面、重新生成任务后求解。真实项目工期及该 7 天空档是否全部消失尚未重算验证；养生、转场、真实前置及移交条件仍可能导致合理等待。
