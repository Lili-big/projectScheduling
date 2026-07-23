---

description: "架梁双幅线路示意图优化实施任务"
---

# 任务清单：架梁双幅线路示意图优化

**输入**：`03-requirements/specs/060-girder-line-schematic/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/line-graph-schematic-ui.md` 和 `quickstart.md`

**实施边界**：不新增 API、持久化结构或依赖；只调整派生线路图、既有诊断行为和现有页面展示。

## Phase 1：用户故事 1 - 清晰查看双幅线路关系（优先级：P1）

**目标**：把 ZK 左幅、K 右幅展示为两条连续平行主线；路基、桥梁、隧道、梁场和 AK/BK/B1K 支线关系一眼可辨，同时保持紧凑单屏总览。

**独立测试**：使用包含 ZK/K 主线、AK/BK/B1K 支线、单幅缺失节点、长名称和梁场的前端夹具，验证主线与支线分类、无占位框、类型样式、名称悬浮全称和梁场外置均符合展示契约。

- [x] T001 [P] [US1] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 增加线路示意图源代码契约回归，覆盖 ZK/K 双主线、AK/BK/B1K 支线层、单幅无节点不占位、路基无图标、桥隧粗线、梁场外置、名称无边框错行省略及悬浮全称。
- [x] T002 [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/LineGraphView.tsx` 将节点按标准化 `alignment_code` 派生为 ZK/K 主线和互通支线，按 `spatial_group_id` 保持左右幅对应，移除空幅占位与主线非必要图标，并把梁场锚定为线路外标记。
- [x] T003 [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/styles.css` 实现紧凑双主线布局、压缩路基宽度、增强桥隧线段、支线短连接、无边框错行名称、省略悬浮和梁场外置样式，同时减少标题列及线路区域高度。
- [x] T004 [US1] 在 `04-demo/frontend/` 运行 `node --test tests/girderPlanSimulation.test.mjs`、`npm.cmd run typecheck` 和 `npm.cmd run build`，确认 `04-demo/frontend/src/features/girderPlanSimulation/LineGraphView.tsx` 的展示契约、类型和构建均通过。

**检查点**：不依赖连续梁长度投影改造，也能独立验证双主线、支线、梁场和紧凑视觉表达。

---

## Phase 2：用户故事 2 - 连续梁按三段示意展示（优先级：P1）

**目标**：左右幅分别按本幅结构顺序生成“小里程引桥段—连续结构段—大里程引桥段”，不要求结构累计长度与线路落位长度逐米相等。

**独立测试**：构造左右幅结构长度和桥梁落位长度均不同的连续梁数据，验证每幅独立生成三段、完整覆盖本幅桥梁区间、顺序与源结构关联稳定，且现有真实结构错误仍阻断。

- [x] T005 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 先增加归一化三段投影回归，覆盖左右幅独立比例、三段顺序与 `source_refs`/`beam_demands` 归属、长度差异无诊断，以及缺失跨序、非正长度、缺少前后引桥、多连续区块和连续结构含预制梁需求仍返回原有诊断。
- [x] T006 [US2] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 使用本幅三组结构长度比例投影完整桥梁起止区间，稳定生成 `approach_small`、`continuous`、`approach_large` 三段，并删除 `BRIDGE_SEGMENT_LENGTH_MISMATCH` 及任何等价长度差异提示分支。
- [x] T007 [US2] 运行 `python -m pytest 04-demo/backend/tests/test_girder_plan_simulation_topology.py -q`，确认 `04-demo/backend/app/girder_plan_simulation/topology.py` 的三段投影、左右幅独立性和保留诊断回归全部通过。

**检查点**：有效连续梁可独立形成三段示意节点，长度差异不再改变线路图可用状态；其他结构错误行为不变。

---

## Phase 3：用户故事 3 - 长度差异不阻断计划推演（优先级：P2）

**目标**：只有左右幅或结构落位长度差异时，线路图和方案校验可继续；既有接口、指纹失效链和其他真实阻断诊断保持兼容。

**独立测试**：通过现有 API/服务夹具验证长度差异不产生阻断，三段节点仍经原接口返回；另用既有缺失结构和线路断点反例确认仍阻断，并确认线路图改变后旧方案继续按既有指纹机制失效。

- [x] T008 [P] [US3] 在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 增加跨模块回归，验证长度差异不产生 `BRIDGE_SEGMENT_LENGTH_MISMATCH`、三段节点继续由既有线路图接口返回、仅长度差异不阻断方案校验/运行，以及节点变化仍触发现有线路图指纹和旧方案失效行为。
- [x] T009 [US3] 运行 `python -m pytest 04-demo/backend/tests -q -k "girder_plan_simulation"`，验证 `04-demo/backend/app/girder_plan_simulation/` 的线路图、方案、校验、运行、仓储、指纹和性能相关回归，且单次性能样例仍不超过既有 10 秒门槛。
- [x] T010 [US3] 按 `03-requirements/specs/060-girder-line-schematic/quickstart.md` 第 4 节在 `04-demo/frontend/src/features/girderPlanSimulation/GirderPlanSimulationPanel.tsx` 所在页面完成泸古项目浏览器验收，核对两河口大桥和永宁河特大桥共 12 个三段节点、4 条长度差异诊断归零、ZK/K 主线与 AK/BK/B1K 支线可辨、梁场位置合理、长名称悬浮可见，并如实记录仍存在的范围外 `MILEAGE_OVERLAP` 或 `LINE_GRAPH_GAP`。

**检查点**：线路示意图与计划推演不再被自然长度差异阻断，同时未掩盖任何范围外真实数据问题。

---

## 依赖与执行顺序

### 用户故事依赖

- **US1** 与 **US2** 无共享文件依赖，可并行开始；T001 先于 T002/T003，T005 先于 T006。
- **US3** 依赖 US1、US2 完成，因为它验证后端派生结果、前端展示和既有计划推演链路的整体兼容性。
- T004 依赖 T002、T003；T007 依赖 T006；T009 依赖 T006、T008；T010 依赖 T004、T007、T009。

### 并行机会

- T001 与 T005 可并行编写，目标文件不同且无数据依赖。
- T002 与 T006 可在各自测试准备完成后并行实施，分别修改前端和后端。
- T008 可在 T006 完成后与前端 T003/T004 并行推进。

## 需求覆盖与一致性

| 需求/验收范围 | 覆盖任务 |
|---|---|
| FR-001～FR-004、FR-014～FR-020；US1 全部验收；SC-005、SC-007 | T001～T004、T010 |
| FR-005～FR-009、FR-011；US2 全部验收；SC-001、SC-002、SC-004 | T005～T007、T010 |
| FR-010、FR-012、FR-013；US3 全部验收；SC-003、SC-006 | T008～T010 |
| API、存储和主数据结构保持不变 | T006、T008、T009 |
| 线路图指纹及旧方案失效沿用既有机制 | T008、T009 |
| 不引入 GIS 背景或新依赖 | T001～T004 |

## 实施完成边界

- T001～T010 全部完成且相关验证通过后，才可声明自动化实施完成。
- T010 的泸古项目浏览器验收是独立验收项；若本地项目版本或运行服务不可用，应如实报告为未覆盖，不得用自动化测试替代。
- `MILEAGE_OVERLAP`、`LINE_GRAPH_GAP` 和其他范围外诊断不属于本功能修复内容，不得因本任务隐藏或删除。
