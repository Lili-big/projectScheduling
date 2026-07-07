# 任务清单：桩基钻机墩组两阶段精排

**输入**：来自 `specs/011-drill-group-two-stage-refinement/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/two-stage-refinement-contract.md`、`quickstart.md`

**测试要求**：本功能涉及排程算法、资源变量、CP-SAT 约束、连续性目标和结果契约，必须包含后端回归测试和兼容验证任务。

## Phase 1：准备（共享基础）

**目标**：确认现有入口和测试落点，避免后续实现偏离当前项目结构。

- [X] T001 复核当前同结构同工艺资源规则和路径连续性建模入口：`backend/app/solver.py`
- [X] T002 复核固定资源、最少资源候选和最佳努力精排编排入口：`backend/app/scenario.py`
- [X] T003 [P] 复核现有 scheduler 测试夹具和连续性断言位置：`backend/tests/test_scheduler.py`
- [X] T004 [P] 复核前端结果类型和模拟结果展示兼容点：`frontend/src/types/scheduler.ts`

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立两阶段精排共用的内部实体、聚合、展开和诊断基础；本阶段完成前不得开始用户故事实现。

- [X] T005 在 `backend/app/solver.py` 增加机械钻机墩组内部数据结构和稳定 `group_id` 生成规则
- [X] T006 在 `backend/app/solver.py` 增加旧版机械钻机墩组筛选逻辑，限定旋挖钻、冲击钻、回旋钻且资源池同结构并行上限为 1；Phase 7 的 T052 将移除该参数门槛
- [X] T007 在 `backend/app/solver.py` 增加原任务到机械钻机墩组的聚合工具，保持 `child_task_ids`、聚合工期和候选资源映射
- [X] T008 在 `backend/app/solver.py` 增加线路序列构建工具，按当前结构顺序或墩号排序并区分左右幅、工艺和钻机资源组
- [X] T009 在 `backend/app/solver.py` 增加墩组结果展开回原任务的工具，支持组内拓扑顺序和稳定兜底排序
- [X] T010 在 `backend/app/solver.py` 增加两阶段精排诊断 payload 构建工具，输出粗排节点、细排节点、弧数量和回退原因
- [X] T011 [P] 在 `backend/tests/test_scheduler.py` 增加机械钻机墩组聚合基础测试夹具，覆盖多墩、多桩、多钻机资源类型

**检查点**：内部聚合、线路序列、展开和诊断基础可被后续故事复用。

---

## Phase 3：用户故事 1 - 降低桩机路径建模规模（优先级：P1）

**目标**：在不改变最终任务输出粒度的前提下，将路径排序从全候选节点降为实际分配节点。

**独立测试**：构造包含多个机械钻机墩组和多台同类桩机的场景，验证粗排不产生全量路径环路，细排只对实际分配节点建模，最终任务数量和 ID 不变。

### 用户故事 1 的测试

- [X] T012 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加聚合后最终任务数量、任务 ID 和任务粒度不变的测试
- [X] T013 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加机械钻机墩组细排弧数量较全候选方式减少不少于 60% 的规模测试
- [X] T014 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加人工挖孔不进入机械钻机墩组聚合的测试

### 用户故事 1 的实现

- [X] T015 [US1] 在 `backend/app/solver.py` 实现粗排阶段墩组级资源分配模型，保留资源兼容、资源数量、资源互斥和任务持续时间硬约束
- [X] T016 [US1] 在 `backend/app/solver.py` 将硬里程碑和外部工艺前后置安全上提到墩组边界
- [X] T017 [US1] 在 `backend/app/solver.py` 实现细排阶段固定 `group -> resource` 的实际节点路径排序
- [X] T018 [US1] 在 `backend/app/solver.py` 实现细排 `makespan_tolerance = 0` 的总工期保护
- [X] T019 [US1] 在 `backend/app/solver.py` 将细排结果展开回原任务并生成 `ScheduleResult` 兼容任务列表
- [X] T020 [US1] 在 `backend/app/solver.py` 将两阶段精排接入 `solve_control_priority_schedule()` 的资源路径连续性启用分支
- [X] T021 [US1] 在 `backend/app/scenario.py` 保持固定资源和最少资源候选精排结果来源语义不混淆
- [X] T022 [US1] 在 `backend/tests/test_scheduler.py` 更新或补充 US1 断言，验证 `resource_path_node_count` 与 `resource_path_transition_arc_count` 使用新规模口径

**检查点**：用户故事 1 可独立运行和验证；即使不做跳墩偏好，也能证明建模规模下降且结果兼容。

---

## Phase 4：用户故事 2 - 按墩号改善桩机连续施工（优先级：P2）

**目标**：在粗排资源分配阶段引入相邻换资源和 `1-0-1` 洞洞式跳墩轻量惩罚。

**独立测试**：构造连续墩号和稀疏墩号场景，验证系统减少相邻换机和洞洞式跳墩，并且不补造缺失墩号。

### 用户故事 2 的测试

- [X] T023 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加相邻墩组换资源惩罚测试
- [X] T024 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `1-0-1` 洞洞式跳墩惩罚测试
- [X] T025 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加稀疏墩号序列只按实际存在墩组判断相邻的测试

### 用户故事 2 的实现

- [X] T026 [US2] 在 `backend/app/solver.py` 实现相邻墩组换资源惩罚项并接入粗排目标
- [X] T027 [US2] 在 `backend/app/solver.py` 实现 `1-0-1` 洞洞式跳墩惩罚项并接入粗排目标
- [X] T028 [US2] 在 `backend/app/solver.py` 将相邻换资源和洞洞跳墩原始罚分写入两阶段精排诊断
- [X] T029 [US2] 在 `backend/tests/test_scheduler.py` 补充 US2 集成断言，验证跳墩偏好不破坏硬里程碑和资源互斥

**检查点**：用户故事 2 可独立验证；粗排资源分配已能解释相邻换机和洞洞式跳墩。

---

## Phase 5：用户故事 3 - 保持结果解释和兼容性（优先级：P3）

**目标**：完善两阶段状态、回退、目标关闭、诊断和前端兼容，确保用户能理解结果来源。

**独立测试**：构造细排失败、资源路径连续性关闭、混合桩基任务和硬里程碑场景，验证结果来源、诊断和前端兼容。

### 用户故事 3 的测试

- [X] T030 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加细排失败时返回粗排展开结果并标记回退的测试
- [X] T031 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加资源路径连续性关闭时不构建两阶段路径节点和跳墩软目标的测试
- [X] T032 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加硬里程碑命中组内原任务时展开结果不迟延的测试

### 用户故事 3 的实现

- [X] T033 [US3] 在 `backend/app/solver.py` 实现 `stage2_refined`、`stage2_fallback`、`coarse_only`、`not_applicable` 诊断状态
- [X] T034 [US3] 在 `backend/app/solver.py` 实现细排失败或超时后的粗排展开回退路径
- [X] T035 [US3] 在 `backend/app/solver.py` 对接目标建模门控，确保资源路径连续性关闭时跳过跳墩软目标和细排路径排序
- [X] T036 [US3] 在 `backend/app/models.py` 补充或明确保留两阶段诊断字段的兼容类型口径，保持旧 payload 可用
- [X] T037 [US3] 在 `frontend/src/types/scheduler.ts` 补充两阶段诊断字段的可选类型，确保旧结果和新结果均可解析
- [X] T038 [US3] 在 `frontend/src/app/App.tsx` 增加两阶段诊断字段的安全读取或忽略保护，不改变任务列表和甘特图粒度
- [X] T039 [US3] 在 `backend/tests/test_scheduler.py` 补充 US3 结果来源和诊断字段断言，覆盖细排成功、细排回退和不适用状态

**检查点**：全部用户故事均可独立运行和验证；结果来源、诊断和前端兼容完整。

---

## Phase 6：收尾与横切事项

**目标**：完成文档、回归和 Spec Kit 门禁复核。

- [X] T040 [P] 更新算法说明文档以解释两阶段墩组精排边界：`docs/固定资源满足分支详细排程算法文档_v1.6.md`
- [X] T041 [P] 更新精排目标函数文档中资源路径连续性和只读诊断边界：`docs/精排目标函数算法需求文档_v4.0.md`
- [X] T042 运行后端排程测试并记录结果：`backend/tests/test_scheduler.py`
- [X] T043 运行前端构建兼容验证并记录结果：`frontend/src/types/scheduler.ts`
- [X] T044 运行快速验证流程并对照预期结果：`specs/011-drill-group-two-stage-refinement/quickstart.md`
- [X] T045 检查 Spec Kit 门禁、任务完成状态和剩余风险：`specs/011-drill-group-two-stage-refinement/tasks.md`

---

## Phase 7：MVP 简化变更（待确认后实施）

**目标**：按用户 2026-07-07 的补充口径，移除 `same_structure_parallel_limit = 1` 作为机械桩基墩组粗排门槛，并将固定资源主链路改为直接进入第一阶段精排。

**独立测试**：构造机械钻机资源未配置、配置为 0 或配置为大于 1 的场景，验证仍进入墩组精排且同一机械墩组内原任务使用同一台对应类型命名资源；构造人工挖孔多资源场景，验证不被单资源墩组规则限制；构造固定资源成功场景，验证主链路不先调用池级最短工期排序；构造固定资源第一阶段失败场景，验证当前资源主结果返回失败并尝试资源建议。

### MVP 简化的测试

- [X] T046 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加机械钻机资源未配置 `same_structure_parallel_limit` 时仍进入墩组精排的测试
- [X] T047 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加机械钻机资源 `same_structure_parallel_limit = 0` 或大于 1 时仍进入墩组精排的测试
- [X] T048 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加同一机械桩基墩组内原任务显式继承同一命名资源的测试
- [X] T049 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加人工挖孔桩多资源并行不受机械墩组单资源规则限制的测试
- [X] T050 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加固定资源成功场景不先调用 `solve_capacity_shortest_schedule()` 的编排测试
- [X] T051 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加固定资源第一阶段精排失败后返回当前资源失败并尝试资源建议的测试，验证不回退展示池级最短工期或当前资源最佳努力结果

### MVP 简化的实现

- [X] T052 [US1] 在 `backend/app/solver.py` 移除 `_build_drill_group_nodes()` 中对 `_effective_same_structure_parallel_limit(resources) == 1` 的聚合门槛，仅保留旋挖钻、冲击钻、回旋钻和命名资源可用性判断
- [X] T053 [US1] 在 `backend/app/solver.py` 增加机械桩基墩组显式单命名资源约束，确保组内所有原任务选择同一台 eligible resource
- [X] T054 [US3] 在 `backend/app/solver.py` 确保 `manual_pile_team` 不进入机械墩组，也不参与 T053 的组内单资源约束
- [X] T055 [US1] 在 `backend/app/solver.py` 调整两阶段触发诊断，区分“无机械墩组”“路径连续性目标关闭”“机械墩组已进入第一阶段但无需第二阶段”
- [X] T056 [US1] 在 `backend/app/scenario.py` 将固定资源主链路改为直接调用 `solve_control_priority_schedule()` 第一阶段精排，不再先执行池级最短工期排序
- [X] T057 [US3] 在 `backend/app/scenario.py` 将第一阶段精排失败处理为当前资源失败并触发资源建议；池级排序仅作为资源建议测算或内部诊断辅助，并更新 `schedule_source`、`performance_path`、`solver_call_count` 语义
- [X] T058 [US2] 在 `backend/app/solver.py` 确保第二阶段路径精排仅在第一阶段存在旋挖钻、冲击钻、回旋钻机械桩基墩组且资源路径连续性目标启用时触发
- [X] T059 [P] 更新 `docs/固定资源满足分支详细排程算法文档_v1.6.md`，说明固定资源主链路直接精排、第一阶段失败返回失败并尝试资源建议、池级排序不作失败兜底展示
- [X] T060 [P] 更新 `docs/精排目标函数算法需求文档_v4.0.md`，说明机械桩基墩组不再依赖 `same_structure_parallel_limit` 且人工挖孔例外

### MVP 简化的验证

- [X] T061 运行后端排程测试并记录结果：`backend/tests/test_scheduler.py`
- [X] T062 运行前端构建兼容验证并记录结果：`frontend/src/types/scheduler.ts`
- [X] T063 检查 Spec Kit 门禁、任务完成状态和剩余风险：`specs/011-drill-group-two-stage-refinement/tasks.md`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 基础能力**：依赖准备阶段完成，阻塞所有用户故事。
- **Phase 3 用户故事 1**：依赖基础能力完成，是 MVP。
- **Phase 4 用户故事 2**：依赖基础能力完成；建议在 US1 后接入，便于复用粗排模型。
- **Phase 5 用户故事 3**：依赖 US1 的两阶段主链路；部分测试可与 US2 并行准备。
- **Phase 6 收尾**：依赖目标用户故事完成。
- **Phase 7 MVP 简化变更**：依赖 Phase 1-6 当前实现完成；确认后作为同一功能的规则收敛迭代实施。

### 用户故事依赖

- **US1（P1）**：完成后即可证明建模规模下降和结果粒度兼容，是建议 MVP。
- **US2（P2）**：依赖粗排资源分配模型，增强资源分配质量。
- **US3（P3）**：依赖主链路和诊断基础，完善回退与兼容。

### 单个故事内部顺序

- 测试任务先于实现任务。
- 内部数据结构先于粗排和细排模型。
- 粗排模型先于细排模型。
- 细排模型先于结果展开和结果来源标记。
- 后端契约稳定后再补前端类型和展示。

### 并行机会

- T003、T004 可与 T001、T002 并行。
- T011 可与 T005-T010 中非同文件任务并行度有限；由于核心集中在 `solver.py`，实现时应串行合并。
- US1 的 T012-T014 可并行编写测试。
- US2 的 T023-T025 可并行编写测试。
- US3 的 T030-T032 可并行编写测试。
- T040、T041 可与最终验证任务并行，但应在实现行为稳定后完成。

---

## 并行示例：用户故事 1

```text
Task: "T012 在 backend/tests/test_scheduler.py 增加最终任务粒度不变测试"
Task: "T013 在 backend/tests/test_scheduler.py 增加细排弧数量减少规模测试"
Task: "T014 在 backend/tests/test_scheduler.py 增加人工挖孔不聚合测试"
```

## 并行示例：用户故事 2

```text
Task: "T023 在 backend/tests/test_scheduler.py 增加相邻换资源惩罚测试"
Task: "T024 在 backend/tests/test_scheduler.py 增加 1-0-1 洞洞跳墩惩罚测试"
Task: "T025 在 backend/tests/test_scheduler.py 增加稀疏墩号相邻判断测试"
```

## 并行示例：用户故事 3

```text
Task: "T030 在 backend/tests/test_scheduler.py 增加细排失败回退测试"
Task: "T031 在 backend/tests/test_scheduler.py 增加目标关闭跳过路径建模测试"
Task: "T032 在 backend/tests/test_scheduler.py 增加硬里程碑组内任务测试"
```

---

## 实施策略

### MVP 优先（仅用户故事 1）

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1 的测试与实现。
3. 验证两阶段主链路能降低路径弧数量，并展开回原任务。
4. 若 US1 验证通过，再进入 US2 和 US3。

### 增量交付

1. US1：先解决规模爆炸和输出兼容。
2. US2：增加相邻换资源和洞洞式跳墩偏好。
3. US3：完善细排回退、目标关闭、诊断字段和前端兼容。
4. MVP 简化变更：移除 `same_structure_parallel_limit` 聚合门槛，固定资源主链路直接进入第一阶段精排。
5. 收尾：更新算法文档，运行后端测试和前端构建，准备 `$speckit-converge`。

---

## Phase 8：第二阶段稀疏路径弧优化

**目标**：按用户 2026-07-07 的补充口径，将机械钻机第二阶段路径细排从单资源全连接弧优化为墩号窗口稀疏弧，降低 `AddCircuit` 建模规模。

- [X] T064 [US1] 在 `backend/tests/test_scheduler.py` 增加机械钻机第二阶段稀疏路径弧测试，覆盖同幅前后 2 个墩与前后 2 个墩左右幅候选。
- [X] T065 [US1] 在 `backend/app/solver.py` 实现机械钻机路径转移候选过滤，仅保留同桥同构件同工艺下墩号距离不超过 2 的同幅或左右幅转移。
- [X] T066 [US3] 运行后端排程回归测试，验证稀疏弧不破坏两阶段成功、回退、目标关闭和人工挖孔例外场景。

