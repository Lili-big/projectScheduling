# 任务清单：进度锁定重排三步闭环

**输入**：`specs/040-progress-forecast-closed-loop/` 下的规格、计划、研究、数据模型、接口契约和快速验证文档。

**测试要求**：本功能修改滚动排程边界、共享响应和前端闭环，三个用户故事均必须包含可复现测试；不得只以生产构建代替规则测试。

## Phase 1：准备与基线保护

**目标**：保护 039 和其他用户改动，记录当前闭环行为与回归基线。

- [x] T001 检查 `git status --short` 和现有差异，在 `specs/040-progress-forecast-closed-loop/quickstart.md` 记录本功能允许修改的文件及必须保护的 039/无关改动
- [x] T002 运行现有 `backend/tests/test_progress_forecast.py`、`backend/tests/test_plan_control_api.py`、`frontend/tests/progressDateDefaults.test.mjs` 和前端构建，将基线结果记录到 `specs/040-progress-forecast-closed-loop/quickstart.md`

---

## Phase 2：共享契约与基础规则

**目标**：先固定向后兼容的数据结构和前端可测试规则入口，阻塞后续三个用户故事。

- [x] T003 在 `backend/app/models.py` 增加 `ForecastTaskExecutionState`、`ForecastExecutionSummary`、`CriticalNodeEvidence`、`CriticalNodeForecast`，并以默认值扩展 `ForecastTaskState` 与 `ForecastSchedule`
- [x] T004 [P] 在 `frontend/src/types/scheduler.ts` 同步任务执行状态、执行摘要、关键节点、证据和预测兼容字段
- [x] T005 [P] 在 `frontend/src/features/planControl/progressWorkflow.ts` 建立进度行问题、未保存变更和三步状态的纯函数类型与空实现骨架
- [x] T006 [P] 在 `backend/tests/test_plan_control_repository.py` 增加不含新增字段的 `plan-control/v1` 历史预测读取和新增字段持久化往返测试
- [x] T007 在 `backend/app/services/plan_control_repository.py` 验证新增默认字段无需 schema 迁移并修复发现的兼容读取问题，不重写历史存储文件

**检查点**：旧计划管控数据可读取，新旧前端类型对齐，后续故事可复用同一预测响应。

---

## Phase 3：用户故事 1 - 保存可用于预测的实际进度（优先级：P1）

**目标**：保存前定位阻断错误，成功后明确形成快照并解锁第二步，失败时不冒充已保存。

**独立测试**：使用晚于状态日期、日期倒置、进行中缺少剩余工期、暂停缺少恢复日期和完全有效五类输入，验证任务行问题、保存状态、数据质量警告、快照修订及步骤解锁。

- [x] T008 [P] [US1] 在 `frontend/tests/progressWorkflow.test.mjs` 增加五类任务状态、未来日期、日期倒置、工程量/比例、暂停恢复条件和未保存变更的规则测试
- [x] T009 [P] [US1] 在 `backend/tests/test_progress_forecast.py` 增加暂停任务缺少恢复日期仍可保存但产生数据质量警告、未来实际日期阻断和有效暂停任务的保存测试
- [x] T010 [US1] 在 `frontend/src/features/planControl/progressWorkflow.ts` 实现与后端一致的行级阻断问题、脏状态比较和第一/第二步解锁推导
- [x] T011 [US1] 在 `backend/app/services/progress_forecast.py` 补齐暂停任务缺少恢复日期的数据质量警告和任务可定位的最终权威校验，保持历史快照读取兼容
- [x] T012 [P] [US1] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 接入行级错误、未保存修改提示、保存成功快照摘要，并让三个步骤始终可见而非条件隐藏
- [x] T013 [US1] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 区分网络不可达、保存校验、修订冲突和存储失败提示，失败时明确“未形成进度快照、未进入重排”
- [x] T014 [US1] 在 `frontend/src/styles.css` 增加三步状态、行级错误、未保存和步骤阻断的样式，保持 351 项分页表格可用

**检查点**：用户故事 1 可独立演示“有效保存才解锁”，不依赖 CP-SAT 重排成功。

---

## Phase 4：用户故事 2 - 锁定实绩并重排剩余计划（优先级：P1）

**目标**：把现有滚动预测明确为业务动作，完整表达五类任务锁定边界并返回执行摘要。

**独立测试**：同一快照包含已完成、进行中、暂停、未开始和取消任务；断言实际日期不改、进行中原资源和剩余段、暂停恢复日、未来开始日、取消依赖诊断、资源数量不增且只执行一次求解。

- [x] T015 [P] [US2] 在 `backend/tests/test_progress_forecast.py` 增加五类任务执行状态、锁定字段、执行摘要计数和历史/未来任务完整性测试
- [x] T016 [P] [US2] 在 `backend/tests/test_progress_forecast.py` 增加进行中任务固定原资源、暂停任务不早于恢复日期、缺少恢复日期时预测无法判断、未开始任务不早于状态日期和取消依赖诊断测试
- [x] T017 [P] [US2] 在 `backend/tests/test_progress_forecast.py` 增加当前趋势资源数量/基准顺序不变、无自动增配且每次预测只调用一次 `solve_schedule` 的测试
- [x] T018 [US2] 在 `backend/app/services/progress_forecast.py` 为历史与预测任务填充 `progress_status`、`execution_state`、命名资源、剩余工期和任务诊断
- [x] T019 [US2] 在 `backend/app/services/progress_forecast.py` 生成 `ForecastExecutionSummary`，补齐取消依赖与暂停恢复诊断，并保持 `as_is` 一次求解和既定资源顺序
- [x] T020 [P] [US2] 在 `backend/tests/test_plan_control_api.py` 增加滚动预测响应执行摘要、任务锁定字段、无可行未来但保留历史实绩和错误状态的接口测试
- [x] T021 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 将第二步主操作改为“锁定实绩并重排剩余计划”，展示五类任务数量、锁定规则、求解中/失败/过期和重新执行状态
- [x] T022 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 将历史实际与未来预测表补充任务执行状态和资源信息，并确保无可行未来时仍展示已锁定实绩
- [x] T023 [US2] 在 `frontend/src/styles.css` 增加执行摘要、锁定说明和历史/未来任务状态样式

**检查点**：用户故事 2 可独立回答“哪些事实锁定、哪些剩余工作重排、当前趋势是否得到可行计划”。

---

## Phase 5：用户故事 3 - 查看关键节点预警并进入调整（优先级：P1）

**目标**：在历史与未来合并计划上重算项目完工和里程碑，展示结构化风险、证据和行动入口。

**独立测试**：覆盖节点全部已完成、全部未来、历史与未来混合、缓冲 3 天/0 天、延期、目标已逾期、任务不匹配和剩余求解不可用场景。

- [x] T024 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加项目完工及强制里程碑的实际、预测、合并和无法判断日期来源矩阵测试
- [x] T025 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加项目完工使用活动计划基准完成日期、缓冲大于 3 天、0–3 天、负缓冲、目标已逾期的四态边界与项目风险汇总一致性测试
- [x] T026 [P] [US3] 在 `backend/tests/test_progress_forecast.py` 增加决定节点日期的任务、瓶颈资源、数据质量和求解失败证据测试，断言不生成无事实来源的原因
- [x] T027 [US3] 在 `backend/app/solver.py` 抽取可复用的里程碑范围匹配与已排任务节点评估纯函数，保持现有求解目标、约束和 `milestone_results` 回归不变
- [x] T028 [US3] 在 `backend/app/services/progress_forecast.py` 使用历史实际与未来预测合并结果生成项目完工和里程碑 `CriticalNodeForecast`，并同步更新兼容摘要
- [x] T029 [US3] 在 `backend/app/services/progress_forecast.py` 生成确定性节点证据、按风险/强制级别排序，并使项目级 `risk_status` 与节点明细一致
- [x] T030 [P] [US3] 在 `backend/tests/test_plan_control_api.py` 增加 `critical_nodes`、证据结构、历史兼容空列表、过期预测和无法判断节点的接口测试
- [x] T031 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 增加第三步风险摘要、关键节点表、日期来源、偏差、缓冲、证据和四态空/错/过期展示
- [x] T032 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现从节点定位相关任务和进入既有调整方案比选，保持三类策略与推荐规则不变
- [x] T033 [US3] 在 `frontend/src/styles.css` 增加关键节点四态、证据展开、任务定位和窄屏布局样式

**检查点**：用户故事 3 可独立回答“哪个节点有风险、差多少天、为什么、下一步查看哪里或如何调整”。

---

## Phase 6：收尾、回归与收敛

**目标**：验证三步闭环、旧数据兼容、既有排程不回归，并完成 Spec Kit 收敛。

- [x] T034 在 `frontend/package.json` 保持并复用 Node 规则测试脚本，运行 `npm.cmd --prefix frontend test` 验证 039 与 040 前端规则
- [x] T035 [P] 运行 `backend/tests/test_progress_forecast.py`、`backend/tests/test_plan_control_repository.py`、`backend/tests/test_plan_control_api.py` 并记录结果到 `specs/040-progress-forecast-closed-loop/quickstart.md`
- [x] T036 [P] 运行 `backend/tests/test_scheduler.py`、`backend/tests/test_ai_resource_scheduling_assistant.py`，确认里程碑公共评估没有改变初始排程和 AI 三方案求解
- [x] T037 [P] 运行 `npm.cmd --prefix frontend run build` 验证 TypeScript 和生产构建
- [x] T038 按 `specs/040-progress-forecast-closed-loop/quickstart.md` 完成浏览器六场景验证，重点检查无快照时入口、未来日期行级提示、一次重排、节点预警和旧预测失效
- [x] T039 检查 `.local-data/plan-control-store.json` 未进入 Git、历史文件未被重写、敏感配置未输出，并运行 `git diff --check`
- [x] T040 运行 `$speckit-converge` 对照 `specs/040-progress-forecast-closed-loop/spec.md`、`plan.md`、`tasks.md` 和实际代码补齐遗漏

---

## 依赖与执行顺序

- Phase 1 → Phase 2；共享模型与前端规则骨架阻塞所有用户故事。
- US1 → US2 → US3；第二步依赖有效快照，第三步依赖有效重排结果。
- 每个故事中的测试先于对应实现；标记 `[P]` 的测试或类型任务位于不同文件，可并行执行。
- Phase 6 依赖三个故事完成；T035、T036、T037 可并行。

## 并行机会示例

- US1：T008 前端规则测试与 T009 后端校验测试可并行；T012 页面接入必须等待 T010。
- US2：T015、T016、T017 可并行设计测试；T021 可在 T019 契约稳定后实施。
- US3：T024、T025、T026 可并行编写；T031 可在 T028/T029 响应稳定后实施。
- 收尾：T035、T036、T037 可并行运行，浏览器验证 T038 在三者通过后执行。

## 实施策略

1. **MVP-1**：完成 US1，使用户明确知道进度是否真正保存及下一步是什么。
2. **MVP-2**：完成 US2，把已有算法能力变成可见、可验证的锁定重排动作。
3. **核心闭环**：完成 US3，将重排结果转成关键节点预警和行动入口。
4. **兼容收尾**：验证旧计划数据、039 日期默认、初始排程和 AI 三方案均不回归。

## 格式校验

- 共 40 项任务，编号 T001–T040 连续。
- 用户故事任务均包含 `[US1]`、`[US2]` 或 `[US3]`。
- 所有任务均包含明确文件路径或验证文档路径。

