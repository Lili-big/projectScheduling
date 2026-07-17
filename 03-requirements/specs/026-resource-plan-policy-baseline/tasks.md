# 任务清单：三方案资源策略基线与 LLM 校验

**输入**：`specs/026-resource-plan-policy-baseline/` 下的规格、计划、研究、数据模型、契约和快速验证文档。

**测试要求**：资源规则和 LLM 回退行为必须具有可复现后端测试；前端执行构建回归但不计划修改。

## Phase 1：准备（共享基础）

- [x] T001 检查当前工作区差异并保护无关改动，实施范围限定于 `backend/app/services/ai_resource_scheduling_assistant.py`、`backend/app/services/ai_resource_explainer.py`、`backend/tests/test_ai_resource_scheduling_assistant.py` 和 `specs/026-resource-plan-policy-baseline/`
- [x] T002 核对默认场景任务资源映射、控制墩、连续梁组、主墩字段和资源上限，并在 `backend/tests/test_ai_resource_scheduling_assistant.py` 建立测试事实

## Phase 2：基础能力（阻塞前置）

- [x] T003 在 `backend/app/services/ai_resource_scheduling_assistant.py` 建立资源工作量状态汇总，覆盖 `ACTIVE`、`UNUSED_OR_UNMAPPED`、`DISABLED`、`UNLIMITED`、`DATA_INVALID`
- [x] T004 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现确定性三版基线构建入口
- [x] T005 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现三版草案统一校验
- [x] T006 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 建立三版完整性、归零、单调性和上限断言

## Phase 3：用户故事 1 - 未使用工艺不分配资源（P1）

- [x] T007 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加单一桩基工艺有工作量、其他工艺预配置非零的测试
- [x] T008 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加未映射、零累计工期和连续梁无工作量归零测试
- [x] T009 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 按任务工艺独立汇总桩基工作量并强制零工作量归零
- [x] T010 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 以项目基线替换未使用工艺继承固定样例的行为

## Phase 4：用户故事 2 - 稳定、可解释的项目基线（P1）

- [x] T011 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加控制墩和墩柱三档公式测试
- [x] T012 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加承台、盖梁匹配系数测试
- [x] T013 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加连续梁工作量和班组归零测试
- [x] T014 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加通用资源三档、单调性和上限测试
- [x] T015 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现墩柱、承台、盖梁和连续梁专项公式
- [x] T016 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现通用三档基线与统一边界裁剪
- [x] T017 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将基线硬规则写入现有六分区 LLM 上下文且保持 025 下载兼容

## Phase 5：用户故事 3 - LLM 输出可控且失败可回退（P2）

- [x] T018 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加未知资源、负数、非整数、超上限和策略类型校验测试
- [x] T019 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加首次非法后携带结构化错误重试成功测试
- [x] T020 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加持续非法回退到确定性基线测试
- [x] T021 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 验证现有方案字段和求解前不推荐边界
- [x] T022 [US3] 在 `backend/app/services/ai_resource_explainer.py` 更新提示约束，明确项目基线、归零、上限、字符串策略和禁止求解前推荐
- [x] T023 [US3] 在 `backend/app/services/ai_resource_explainer.py` 增加一次携带 `validation_errors` 的纠错调用能力
- [x] T024 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 串联首次生成、严格校验、一次纠错和基线回退
- [x] T025 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 禁止为接纳 LLM 输出扩大原始 `max_quantity`

## Phase 6：收尾与横切验证

- [x] T026 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q`，29 项通过
- [x] T027 [P] 运行 `python -m pytest backend/tests -q`，216 项通过
- [x] T028 [P] 在 `frontend/` 运行 `npm.cmd run build`，TypeScript 与生产构建通过
- [x] T029 按 `specs/026-resource-plan-policy-baseline/quickstart.md` 复核默认项目、合法输出、纠错成功和持续非法回退路径
- [x] T030 运行 `$speckit-converge` 对照规格、计划、任务和实际代码完成收敛检查

## 依赖与实施策略

- 资源工作量状态、基线和校验是三个用户故事的共享前置。
- US1 先消除零工作量扩充，US2 建立项目化基线，US3 接入 LLM 纠错与稳定回退。
- 三方案生成不修改 CP-SAT，也不产生求解前最终推荐。

## 格式校验

- 共 30 项任务，全部完成并保持编号连续。
- 用户故事任务均包含对应 `[US1]`、`[US2]` 或 `[US3]`。
- 每项任务均指向明确文件或验证命令。
