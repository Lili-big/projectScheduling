# 任务清单：任务结构物参数与工程量拆分

**输入**：来自 `specs/030-task-parameter-quantity-split/` 的规格、研究、数据模型、接口契约和验证指南

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/task-parameter-quantity-contract.md`、`quickstart.md`

**测试要求**：本功能修改共享字段和墩柱工期计算，所有用户故事都必须包含先行测试或可复现验证；实施后必须运行后端回归、前端生产构建和页面联调。

**组织方式**：任务按用户故事分组，确保参数/工程量拆分、平均墩高、工效切换与历史兼容均可独立验证。

## Phase 1：准备（共享基础）

**目标**：确认工作区边界和当前契约，避免覆盖 Spec 028、029 及其他用户修改。

- [X] T001 记录当前 `git status`、`.specify/feature.json` 和 `specs/030-task-parameter-quantity-split/plan.md` 所列目标文件，实施时保留既有 028/029 修改
- [X] T002 [P] 对照 `specs/030-task-parameter-quantity-split/contracts/task-parameter-quantity-contract.md` 复核 `backend/app/models.py`、`frontend/src/types/scheduler.ts`、`netlify/demo-functions/api.mts` 的现有字段和默认值

---

## Phase 2：基础能力（阻塞前置）

**目标**：先建立向后兼容的共享数据契约；本阶段完成前不得开始业务故事实现。

- [X] T003 在 `backend/app/models.py` 为 `ComponentModel`、`UpperStructureComponent`、`Task` 增加默认可空 `structure_parameter_label`
- [X] T004 [P] 在 `frontend/src/types/scheduler.ts` 为 `ComponentModel`、`UpperStructureComponent`、`Task` 同步可空 `structure_parameter_label`
- [X] T005 [P] 在 `netlify/demo-functions/api.mts` 为参考实现中的 `ComponentModel`、上部结构对象和 `Task` 同步可空 `structure_parameter_label`

**检查点**：旧 JSON 缺失新字段时仍可通过模型和类型校验，三个运行边界具备相同增量字段。

---

## Phase 3：用户故事 1 - 分开核验结构参数与工程量（优先级：P1）

**目标**：十类当前实际生成任务都能分别输出稳定的结构物参数和纯工程量，并在任务视图拆列展示。

**独立测试**：导入当前桥梁样例并生成任务图，检查八类下部任务与现浇箱梁、现浇连续梁任务；承台分别显示 `6.25m × 1.5m × 1.8m` 和 `1个`，所有工程量文本均不混入结构尺寸或形式。

### 用户故事 1 的测试

- [X] T006 [P] [US1] 在 `backend/tests/test_bridge_import.py` 增加八类下部构件参数摘要、纯工程量、真实数量和接口响应契约测试
- [X] T007 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加十类当前任务覆盖测试，断言现浇箱梁/连续梁参数上下文、块/段/联单位及参数摘要不参与工期

### 用户故事 1 的实现

- [X] T008 [US1] 在 `backend/app/bridge_import.py` 拆分尺寸/形式摘要与数量标签，补齐桩型、桩径、柱径、柱数、尺寸和结构形式的结构化属性
- [X] T009 [US1] 在 `backend/app/scenario.py` 将 `structure_parameter_label` 写入下部及上部 `Task`，并按 `quantity_source` 生成只含数值和单位的 `quantity_label`
- [X] T010 [US1] 在 `backend/app/scenario.py` 为现浇箱梁和连续梁/连续刚构任务透传结构形式、支座范围、跨径组合与节段类型，保持当前任务生成范围不变
- [X] T011 [P] [US1] 在 `backend/app/scenario_data.py` 为默认结构构件补齐可用参数摘要和纯工程量标签，保持默认任务数量不变
- [X] T012 [US1] 在 `frontend/src/app/App.tsx` 将任务表拆成“结构物参数”“工程量”两列，优先展示任务摘要、缺失时从 `properties` 派生、仍缺失时显示 `-`
- [X] T013 [P] [US1] 在 `frontend/src/styles.css` 调整任务表新增列的宽度、换行和横向滚动，保证工期表达式仍可完整查看
- [X] T014 [US1] 在 `netlify/demo-functions/api.mts` 对齐十类参考任务的参数摘要、纯工程量、真实构件数量和上部任务上下文，不启用未生成类型

**检查点**：只完成 US1 时，任务视图已能独立展示两列，当前十类任务契约完整；墩柱工期仍待 US2 切换到平均高度。

---

## Phase 4：用户故事 2 - 按平均墩高计算墩柱工期（优先级：P1）

**目标**：统一高度、多柱独立高度和历史总高度场景均按用户确认的平均墩高生成墩柱工程量与工期。

**独立测试**：双柱每根 10m、标准节高 4.5m、每节 7 天时，任务工程量为 10m、节数为 3、工期为 21 天；逐柱 `[8,10,12]` 得到 10m；无有效高度形成明确诊断。

### 用户故事 2 的测试

- [X] T015 [P] [US2] 在 `backend/tests/test_bridge_import.py` 增加导入双柱墩不再执行 `height × count`、摘要使用“柱径”和统一高度视为平均高度的测试
- [X] T016 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加统一高度、逐柱高度、历史总高度兼容、无有效高度诊断及 `10m → 3节 → 21天` 测试

### 用户故事 2 的实现

- [X] T017 [US2] 在 `backend/app/bridge_import.py` 将新导入墩柱的基础工程量改为平均墩高，并保留 `height_m`、柱数和未来逐柱高度属性
- [X] T018 [US2] 在 `backend/app/scenario.py` 实现逐柱有效高度平均、统一结构化高度优先、历史总高度不误用的取值顺序，并让无有效高度走现有错误诊断
- [X] T019 [US2] 在 `frontend/src/app/App.tsx` 对齐本地工效切换的平均墩高取值和节数/工期表达式，禁止重新乘以柱数或解析旧混合文本
- [X] T020 [US2] 在 `netlify/demo-functions/api.mts` 对齐平均墩高取值优先级、无效值处理和标准节工期计算

**检查点**：US2 完成后，墩柱工程量与所有按米/按节工效使用同一平均高度，求解器只接收更新后的任务工期。

---

## Phase 5：用户故事 3 - 切换工效并兼容历史数据（优先级：P2）

**目标**：工效切换只更新工程量与工期；历史数据和计划缺失新字段时可读取、可派生且不改写原文件。

**独立测试**：同一桩基从按米切换到按根后参数摘要不变、工程量变为 `1根`；加载缺少新字段且带旧混合标签的项目/计划不报错，文件哈希不变。

### 用户故事 3 的测试

- [X] T021 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加工效切换后的纯工程量、真实数量、摘要稳定和禁止解析旧混合 `quantity_label` 的测试
- [X] T022 [P] [US3] 在 `backend/tests/test_plan_control_repository.py` 与 `backend/tests/test_plan_control_api.py` 增加缺失新字段的历史计划加载、基准读取和文件哈希不变测试

### 用户故事 3 的实现

- [X] T023 [US3] 在 `backend/app/scenario.py` 为缺少摘要的历史 `ComponentModel` 从结构化 `properties` 派生任务摘要，无法派生时保持空值且不影响有效任务
- [X] T024 [US3] 在 `frontend/src/app/App.tsx` 保证本地工艺/工效切换保留 `structure_parameter_label`，只更新工程量、工期、表达式和资源候选，并沿用旧结果失效链路
- [X] T025 [US3] 在 `netlify/demo-functions/api.mts` 保持旧场景字段可空和结构化属性回退，不从旧 `quantity_label` 反向拆分参数或工程量

**检查点**：全部用户故事可独立验证，现有项目、基准计划和进度反馈链路无需迁移。

---

## Phase 6：收尾与横切事项

**目标**：同步文档并完成后端、前端、参考实现和真实页面的全链路验证。

- [X] T026 [P] 更新 `docs/任务视图页面需求文档_v1.0.md`，补充两列定义、十类映射、平均墩高、工效切换和历史兼容验收口径
- [X] T027 [P] 更新 `docs/项目排程系统整体说明_v1.1.md`，收敛结构参数、工程量与墩柱工期的系统级数据流说明
- [X] T028 运行 `backend/tests/test_bridge_import.py`、`backend/tests/test_scheduler.py`、`backend/tests/test_plan_control_repository.py`、`backend/tests/test_plan_control_api.py` 并修复本功能回归
- [X] T029 运行 `npm.cmd run build` 与 `git diff --check`，核验 `frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`、`frontend/src/styles.css` 及全仓格式
- [X] T030 静态核对 `netlify/demo-functions/api.mts` 与 `specs/030-task-parameter-quantity-split/contracts/task-parameter-quantity-contract.md` 的三个共享实体、平均高度和十类任务生成规则
- [X] T031 按 `specs/030-task-parameter-quantity-split/quickstart.md` 完成页面联调，验证两列表头、承台拆分、墩柱 21 天、上下部十类任务、工效切换和旧结果失效
- [X] T032 运行 `python -m pytest backend/tests -q` 全量回归，并对照 `AGENTS.md`、`.specify/memory/constitution.md` 和本功能产物准备 `$speckit-converge` 证据

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 基础能力**：依赖 Phase 1，阻塞全部故事。
- **US1（Phase 3）**：依赖 Phase 2，先交付两列和十类任务的基础契约。
- **US2（Phase 4）**：依赖 Phase 2；与 US1 的部分测试可并行，但最终页面验收依赖 US1 两列。
- **US3（Phase 5）**：依赖 Phase 2；历史兼容测试可提前，完整工效切换验收依赖 US1/US2。
- **Phase 6 收尾**：依赖三个故事完成。

### 用户故事依赖

- **US1（P1）**：基础字段完成后即可独立实现和验证。
- **US2（P1）**：平均墩高算法可独立测试；页面最终展示复用 US1 新列。
- **US3（P2）**：历史字段兼容可独立测试；完整切换行为复用 US1 工程量标签和 US2 平均高度。

### 单个故事内部顺序

- 测试任务先于实现任务。
- 结构源和后端任务生成先于前端、Netlify 镜像。
- 参数摘要与工程量先于工期表达式和页面验收。
- 当前故事完成独立测试后再进入收尾回归。

### 并行机会

- T003、T004、T005 位于不同文件，可在契约确认后并行。
- T006 与 T007、T015 与 T016、T021 与 T022 位于不同测试边界，可分别并行。
- T011、T013 可与对应后端主链工作并行，但集成前必须以同一契约收敛。
- T026 与 T027 可并行更新不同文档。

---

## 并行示例：用户故事 1

```text
Task: "在 backend/tests/test_bridge_import.py 增加八类下部拆分测试"
Task: "在 backend/tests/test_scheduler.py 增加十类任务与上部参数测试"
Task: "在 backend/app/scenario_data.py 补齐默认构件摘要"
Task: "在 frontend/src/styles.css 调整新增列布局"
```

## 并行示例：用户故事 2

```text
Task: "在 backend/tests/test_bridge_import.py 增加导入平均墩高测试"
Task: "在 backend/tests/test_scheduler.py 增加 21 天和边界测试"
```

## 实施策略

### MVP 优先

本功能最小可用范围为 Phase 1、Phase 2、US1 和 US2：用户能看到参数/工程量拆分，同时墩柱工期使用正确平均高度。US3 历史兼容必须在正式合并前完成，但不阻塞首轮页面演示。

### 增量交付

1. 建立可空字段，保证旧数据不失败。
2. 完成 US1，两列与十类任务可核验。
3. 完成 US2，平均墩高和 21 天样例可复现。
4. 完成 US3，工效切换与历史计划兼容闭环。
5. 同步参考实现和文档，执行全量回归与页面验证。

## 备注

- `[P]` 仅用于不同文件且无未完成依赖冲突的任务。
- 未配置发布的 `netlify/demo-functions/api.mts` 作为参考镜像静态核对，不把它描述为当前生产 Functions。
- 不新增依赖、服务、数据库迁移或任务类型。
