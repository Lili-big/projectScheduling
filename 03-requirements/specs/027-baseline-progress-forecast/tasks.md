# 任务清单：基准计划、进度反馈与滚动预测

**输入**：`specs/027-baseline-progress-forecast/` 下的规格、计划、研究、数据模型、接口契约和快速验证文档。

**测试要求**：本功能修改共享模型、持久化、CP-SAT 执行约束和前后端流程，所有用户故事必须包含可复现测试或构建验证。

## Phase 1：准备（共享基础）

**目标**：保护当前 025/026 和用户改动，固定实现入口与测试基线。

- [x] T001 检查 `git status` 和当前差异，记录本功能允许修改的文件并保护无关改动，依据 `specs/027-baseline-progress-forecast/plan.md`
- [x] T002 运行现有资源助手与排程基线测试，记录兼容基线到 `specs/027-baseline-progress-forecast/quickstart.md` 的实施备注
- [x] T003 核对 `.gitignore` 已忽略 `.local-data/`、临时文件、Python/Node 构建产物，不修改无关忽略规则

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立四个用户故事共享的模型、存储和求解执行约束。

- [x] T004 在 `backend/app/models.py` 增加 `TaskExecutionConstraint`、`PlanVersion`、进度快照、更正、预测、调整和计划变更请求响应模型，并给 `ScheduleInput.execution_constraints` 提供默认空列表
- [x] T005 [P] 在 `frontend/src/types/scheduler.ts` 同步计划管控模型、状态枚举、API 请求响应和 `ScheduleInput.execution_constraints`
- [x] T006 [P] 在 `backend/tests/test_plan_control_repository.py` 编写存储 schema、空库、原子往返、损坏文件、活动版本唯一性和修订冲突测试
- [x] T007 在 `backend/app/services/plan_control_repository.py` 实现 `.local-data/plan-control-store.json` 的版本化读取、整体校验、临时文件原子替换和进程内写锁
- [x] T008 [P] 在 `backend/tests/test_scheduler.py` 增加最早开始、固定开始、固定资源、未知任务/资源以及默认空约束不回归测试
- [x] T009 在 `backend/app/solver.py` 将 `execution_constraints` 接入标准求解与相关精排分支，统一校验并应用开始时间和资源分配硬约束
- [x] T010 在 `backend/app/services/progress_forecast.py` 建立领域错误、稳定指纹、ID、时间和状态辅助函数骨架

**检查点**：本地存储和可选执行约束可独立测试；旧 `ScheduleInput` 行为保持不变。

---

## Phase 3：用户故事 1 - 选择并确认基准计划（优先级：P1）

**目标**：从已求解可行方案生成可跨刷新和重启恢复的不可变基准版本。

**独立测试**：确认可行方案后重新创建存储实例，逐字段恢复计划；不可行或 ID 不一致方案返回业务错误。

- [x] T011 [P] [US1] 在 `backend/tests/test_plan_control_repository.py` 增加可行方案基准快照、不可行状态、方案结果 ID 不一致、版本递增和原基准不可变测试
- [x] T012 [P] [US1] 在 `backend/tests/test_plan_control_api.py` 增加创建基准、查询项目摘要、空态、404/409/422/503 映射测试
- [x] T013 [US1] 在 `backend/app/services/progress_forecast.py` 实现基准创建校验和完整 `ScenarioInput`、`GeneratedScheduleInput`、`ScheduleResult`、资源方案快照构建
- [x] T014 [US1] 在 `backend/app/services/plan_control_repository.py` 实现版本号分配、单一活动版本切换、项目摘要和历史版本读取
- [x] T015 [US1] 在 `backend/app/main.py` 增加 `POST /api/plan-control/baselines` 与 `GET /api/plan-control/projects/{project_id}` 路由和错误映射
- [x] T016 [P] [US1] 在 `frontend/src/api/schedulerApi.ts` 增加创建基准和加载计划管控摘要 API
- [x] T017 [P] [US1] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 为已求解可行方案增加“设为基准计划”操作和提交状态
- [x] T018 [US1] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 串联基准确认、确认人/原因输入、成功版本提示和进入计划执行页入口

**检查点**：用户故事 1 可独立演示基准计划持久化，不依赖进度和预测。

---

## Phase 4：用户故事 2 - 按状态日期填报实际进度（优先级：P1）

**目标**：对稳定任务 ID 提交可校验、可更正、可审计的进度快照。

**独立测试**：提交五种任务状态并更正同日快照，验证剩余工期、阻断错误、冲突警告和审计记录。

- [x] T019 [P] [US2] 在 `backend/tests/test_progress_forecast.py` 增加五种任务状态字段矩阵、日期/工程量/比例校验和未知任务测试
- [x] T020 [P] [US2] 在 `backend/tests/test_progress_forecast.py` 增加剩余工程量除以实际工效向上取整、人工剩余工期回退和来源标识测试
- [x] T021 [P] [US2] 在 `backend/tests/test_plan_control_repository.py` 增加同状态日期修订、期望修订号冲突、原值保留和字段级审计测试
- [x] T022 [US2] 在 `backend/app/services/progress_forecast.py` 实现进度标准化、阻断错误、可接受警告、数据质量和剩余工期计算
- [x] T023 [US2] 在 `backend/app/services/plan_control_repository.py` 实现进度快照修订、当前修订切换、更正记录和相关预测过期标记
- [x] T024 [US2] 在 `backend/app/main.py` 增加 `POST /api/plan-control/progress-snapshots` 路由与冲突/校验错误映射
- [x] T025 [P] [US2] 在 `frontend/src/api/schedulerApi.ts` 增加进度快照保存 API
- [x] T026 [P] [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 建立版本摘要、状态日期、任务搜索筛选和五种状态填报表格
- [x] T027 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现动态必填字段、剩余工期来源、错误/警告、更正原因、保存成功和旧预测过期提示

**检查点**：用户故事 2 可从活动版本加载任务并保存、恢复和更正快照。

---

## Phase 5：用户故事 3 - 滚动预测并判断按期风险（优先级：P1）

**目标**：冻结历史事实，复用 CP-SAT 预测剩余计划并展示基准、实际、预测三态和按期风险。

**独立测试**：进度一致、关键任务延迟、取消任务、资源不足和数据缺失场景分别得到预期预测、风险与可信度。

- [x] T028 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加已完成任务冻结、进行中 offset 0、未开始不早于状态日期和剩余网络逻辑转换测试
- [x] T029 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加 `as_is` 原资源、固定资源、基准资源顺序只向后传播测试
- [x] T030 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加进度一致不误报、强制里程碑延期仍返回预测、数据不足和可信度测试
- [x] T031 [P] [US3] 在 `backend/tests/test_plan_control_api.py` 增加预测成功、数据不足、无解、过期输入和存储失败 API 测试
- [x] T032 [US3] 在 `backend/app/services/progress_forecast.py` 实现历史任务冻结、残余任务/逻辑/里程碑/资源网络构建与基准资源顺序提取
- [x] T033 [US3] 在 `backend/app/services/progress_forecast.py` 实现 `as_is` 求解、历史与预测合并、任务三态、里程碑偏差、关键线路和瓶颈诊断
- [x] T034 [US3] 在 `backend/app/services/progress_forecast.py` 实现 `on_track`、`at_risk`、`late`、`insufficient_data` 判断、证据和可信度规则
- [x] T035 [US3] 在 `backend/app/services/plan_control_repository.py` 实现预测保存、输入指纹查重和过期状态持久化
- [x] T036 [US3] 在 `backend/app/main.py` 增加 `POST /api/plan-control/forecasts` 路由
- [x] T037 [P] [US3] 在 `frontend/src/api/schedulerApi.ts` 增加滚动预测 API
- [x] T038 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现预测入口、加载/失败/过期状态、按期结论、风险证据和基准/实际/预测三态表

**检查点**：用户故事 3 能独立回答“按当前趋势能否按期完成以及依据是什么”。

---

## Phase 6：用户故事 4 - 比较调整方案并形成新执行版本（优先级：P2）

**目标**：比较三类受控策略并把用户采用结果保存为新执行版本。

**独立测试**：风险预测生成三类独立结果，单策略失败不阻塞；采用可行结果后新旧版本和变更记录完整。

- [x] T039 [P] [US4] 在 `backend/tests/test_progress_forecast.py` 增加三策略恰好齐全、瓶颈资源增量边界、关键任务优先且资源不变测试
- [x] T040 [P] [US4] 在 `backend/tests/test_progress_forecast.py` 增加单策略失败隔离、确定性推荐、边际收益不足和 LLM 不改结论测试
- [x] T041 [P] [US4] 在 `backend/tests/test_plan_control_repository.py` 增加采用方案、新活动版本、父子关系、来源预测、原版本转历史、重复/过期采用冲突测试
- [x] T042 [P] [US4] 在 `backend/tests/test_plan_control_api.py` 增加生成调整方案和采用方案 API 正常、部分失败、409、422、503 测试
- [x] T043 [US4] 在 `backend/app/services/progress_forecast.py` 实现瓶颈识别、资源增量候选、关键任务优先输入和三策略独立求解
- [x] T044 [US4] 在 `backend/app/services/progress_forecast.py` 实现策略指标比较、强制里程碑优先、边际收益和本地/LLM解释边界
- [x] T045 [US4] 在 `backend/app/services/plan_control_repository.py` 实现调整方案保存、采用事务、新执行版本和 `PlanChangeRecord`
- [x] T046 [US4] 在 `backend/app/main.py` 增加 `POST /api/plan-control/forecasts/{forecast_id}/adjustments` 与 `POST /api/plan-control/adjustments/{proposal_id}/adopt`
- [x] T047 [P] [US4] 在 `frontend/src/api/schedulerApi.ts` 增加调整方案生成和采用 API
- [x] T048 [US4] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现三策略卡、独立状态、指标差异、推荐证据、采用确认和版本切换

**检查点**：四个用户故事形成“选基准—填进度—做预测—采用调整”的完整闭环。

---

## Phase 7：导航、兼容与收尾验证

**目标**：接入应用导航，验证跨模块兼容和 Spec Kit 收敛。

- [x] T049 在 `frontend/src/app/App.tsx` 增加“计划执行与进度”导航和项目场景变化时的临时态失效/持久化摘要重载
- [x] T050 [P] 在 `frontend/src/styles.css` 增加计划版本、进度表、三态对比、风险证据和调整方案响应式样式，不覆盖无关现有样式
- [x] T051 运行 `python -m pytest backend/tests/test_plan_control_repository.py backend/tests/test_progress_forecast.py backend/tests/test_plan_control_api.py -q`
- [x] T052 [P] 运行 `python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py -q` 验证排程与三方案回归
- [x] T053 [P] 在 `frontend/` 运行 `npm.cmd run build` 验证 TypeScript 与生产构建
- [x] T054 按 `specs/027-baseline-progress-forecast/quickstart.md` 完成浏览器闭环验证，包括刷新恢复、进度更正、预测过期、部分策略失败和版本采用
- [x] T055 检查本地持久化文件未进入 Git、敏感配置未写入响应或规格，并运行 `git diff --check`
- [x] T056 运行 `$speckit-converge` 对照 `specs/027-baseline-progress-forecast/spec.md`、`plan.md`、`tasks.md` 与实际实现补齐遗漏

---

## 依赖与执行顺序

- Phase 1 → Phase 2；共享模型、存储与执行约束阻塞所有用户故事。
- US1 → US2 → US3 → US4，业务数据存在显式生命周期依赖，不建议跨故事并行实施。
- 同一故事中的测试设计、前端类型/API 和独立文件可按 `[P]` 并行；同一服务文件落盘必须顺序合并。
- 收尾阶段依赖四个故事完成。

## 并行机会

- 后端测试文件、前端类型/API、页面组件在接口契约固定后可并行。
- T051、T052、T053 可并行运行。
- 存储事务与预测算法分别位于不同模块，但采用流程需要二者接口稳定后再串联。

## 实施策略

1. **MVP-1**：Phase 1–3，先证明已求解方案可成为稳定基准。
2. **MVP-2**：完成 US2，建立可审计进度事实。
3. **核心价值**：完成 US3，可靠回答按期风险。
4. **决策闭环**：完成 US4，形成可比较调整和新执行版本。
5. **收敛**：执行完整回归、浏览器验证和 `$speckit-converge`。

## 格式校验

- 共 56 项任务，编号连续。
- 用户故事任务均包含 `[US1]`、`[US2]`、`[US3]` 或 `[US4]`。
- 每项任务均包含明确文件路径或验证文件路径。
