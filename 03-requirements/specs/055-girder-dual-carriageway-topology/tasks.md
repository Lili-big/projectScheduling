---

description: "架梁双幅线路拓扑实施任务"
---

# 任务清单：架梁双幅线路拓扑

**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[接口契约](./contracts/girder-dual-carriageway-topology.openapi.yaml)、[quickstart.md](./quickstart.md)

**确认门禁**：本清单经用户确认后才进入 `$speckit-implement`；实施期间保护当前工作树的无关修改，不原地改写已确认项目主数据版本。

## Phase 1：共享基础——项目主数据线路落位

**目标**：在不破坏旧 1.0 模板和现有 SQLite 状态的前提下，为双幅投影提供显式、可追溯的线路落位数据。

- [x] T001 [P] 在 `04-demo/backend/tests/test_project_master_workbook.py`、`04-demo/backend/tests/test_contracts_project_master.py` 和 `04-demo/backend/tests/project_master_fixture_helpers.py` 先增加“线路关系”表解析/导出往返、同工点同幅重复、区间反转、未知工点引用及旧 1.0 模板无该表仍可加载的失败/兼容测试。
- [x] T002 [P] 在 `04-demo/backend/tests/test_project_master_repository.py` 和 `04-demo/backend/tests/test_project_master_traceability.py` 先增加 SQLite schema v1→v2 新表迁移、落位保存重载、来源证据和确认版本内容不被回写的持久化测试。
- [x] T003 在 `04-demo/backend/app/contracts/project_master.py`、`04-demo/backend/app/contracts/__init__.py` 和 `04-demo/frontend/src/contracts/projectMaster.ts` 增加 `ProjectMasterRoutePlacement` 及 `ProjectMasterSnapshot.route_placements` 共享模型，落实 side、前缀、分幅里程、空间组、展示顺序和来源校验。
- [x] T004 在 `04-demo/backend/app/project_master/schema.py` 和 `04-demo/backend/app/project_master/repository.py` 将项目主数据 schema 升级为 v2，新增 `route_placements` 表、加载/保存/来源证据和指纹序列化，保证已有数据库只增结构不改确认版本内容。
- [x] T005 在 `04-demo/backend/app/project_master/workbook.py` 增加新版可选“线路关系”工作表、1.0/新版兼容解析与导出，并返回稳定导入诊断；禁止把缺失线路关系静默伪造成源 Excel 行号。

**检查点**：项目主数据可显式保存双幅落位，旧版本仍能加载为空落位集合。

---

## Phase 2：用户故事 1——按左右幅查看项目线路（P1）

**目标**：后端生成 v2 双幅节点，前端固定显示“左幅（ZK）”和“右幅（K）”两行，互通前缀只作为节点属性。

**独立测试**：包含 `ZK/K`、`AK`、`BK`、`B1K` 和同一空间组左右节点的样例只产生两条展示线路，节点幅别和纵向序位正确。

- [x] T006 [P] [US1] 在 `04-demo/backend/tests/girder_plan_simulation_fixture_helpers.py` 和 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 先增加显式落位、结构物幅别兼容落位、`ZK/K→left:ZK/right:K`、单侧互通节点、非桥梁分幅节点和稳定桥梁目标 ID 的拓扑测试。
- [x] T007 [P] [US1] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 先增加固定两行、`AK/BK/B1K` 节点徽标、共享空间组同列、单侧空位不挤乱后续节点及缺数据空态的页面旅程测试。
- [x] T008 [US1] 在 `04-demo/backend/app/contracts/girder_plan_simulation.py` 和 `04-demo/frontend/src/contracts/girderPlanSimulation.ts` 将线路图契约升级为 `girder-plan-line-graph/v2`，为节点增加空间组、展示顺序和 `explicit/inferred` 证据状态，并把 `alignment_code` 明确保留为原始里程前缀。
- [x] T009 [US1] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 实现显式线路落位优先、结构物 `left/right` 兼容推断、主线前缀拆分及桥梁/非桥梁按幅生成节点；兼容推断必须稳定排序并生成证据提示，不创建 `unknown` 替代节点。
- [x] T010 [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/LineGraphView.tsx` 和 `04-demo/frontend/src/features/girderPlanSimulation/styles.css` 使用共享空间组栅格固定渲染两条可横向滚动线路，显示工点类型、原始前缀、格式化里程和交付风险，且空间同行不绘制通行边。

**检查点**：用户故事 1 可独立演示；泸古语义样例只有两条线路且节点归属正确。

---

## Phase 3：用户故事 2——可信的连续性与重叠诊断（P2）

**目标**：只在同幅、同可比较前缀和显式数据内执行严格区间校验，保留真实阻断并消除跨幅/跨前缀误报。

**独立测试**：左右平行区间和不同前缀不产生重叠错误；同幅同前缀真实重叠仍阻断；Excel 同行本身不生成横向边。

- [x] T011 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 先增加跨幅平行、同幅跨前缀、显式同幅同前缀真实重叠、空间同行不连通、人工连接后连通和一对多空间组保留节点的精确断言。
- [x] T012 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_validation.py` 和 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 先增加 `ROUTE_SIDE_MISSING`、`ROUTE_PLACEMENT_INFERRED`、`ROUTE_PLACEMENT_DUPLICATE`、`ROUTE_MILEAGE_*`、`LINE_GRAPH_GAP` 的级别、对象引用和 200 响应诊断契约测试。
- [x] T013 [US2] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 按 `side + mileage_prefix` 重构排序、重叠、间隙和自动相邻边规则，将空间对应与可通行边彻底分离，并保留人工连接方向、移动天数和确认审计。
- [x] T014 [US2] 在 `04-demo/backend/app/girder_plan_simulation/validation.py` 和 `04-demo/frontend/src/features/girderPlanSimulation/adapter.ts` 接入新诊断的计算门禁、中文可定位说明和修正建议，保证只有影响可达性或唯一性的缺口阻断计算。

**检查点**：用户故事 2 可独立验证；误报为 0，真实重叠和未确认断点仍被阻断。

---

## Phase 4：用户故事 3——兼容既有方案并重算（P3）

**目标**：旧项目和方案可加载，可唯一映射的人工顺序保留；梁场改用稳定双幅节点，v1 结果明确失效后重算。

**独立测试**：保存 v1 方案和运行后加载 v2，验证桥梁目标顺序保留、梁场唯一兼容匹配或明确阻断、旧运行 stale、新运行使用 v2 指纹。

- [x] T015 [P] [US3] 在 `04-demo/backend/tests/test_girder_plan_simulation_validation.py`、`04-demo/backend/tests/test_girder_plan_simulation_repository.py` 和 `04-demo/backend/tests/test_project_master_invalidation.py` 先增加旧梁场唯一/多义部署、投影版本与线路落位进入指纹、旧运行失效且历史快照保留的测试。
- [x] T016 [P] [US3] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 先增加既有方案加载、桥梁幅别顺序保留、梁场部署到具体双幅节点、多义部署要求重新选择和重算提示的旅程测试。
- [x] T017 [US3] 在 `04-demo/backend/app/contracts/girder_plan_simulation.py`、`04-demo/backend/app/girder_plan_simulation/validation.py`、`04-demo/frontend/src/contracts/girderPlanSimulation.ts`、`04-demo/frontend/src/features/girderPlanSimulation/YardPlanEditor.tsx` 和 `04-demo/frontend/src/features/girderPlanSimulation/adapter.ts` 为梁场增加可选 `deployment_node_id`，新保存写稳定节点，旧 `alignment_code + mileage_m` 仅做唯一兼容匹配并对多义情况阻断。
- [x] T018 [US3] 在 `04-demo/backend/app/girder_plan_simulation/service.py`、`04-demo/backend/app/girder_plan_simulation/repository.py` 和 `04-demo/frontend/src/features/girderPlanSimulation/GirderPlanSimulationPanel.tsx` 将 v2 投影、线路落位和梁场部署纳入输入指纹、失效与重算流程，保留历史运行和现有桥梁目标顺序，不写回架梁专项或综合排程。

**检查点**：用户故事 3 可独立验证；旧数据安全、当前结果不混用 v1 拓扑。

---

## Phase 5：共享契约冻结与端到端验证

**目标**：同步公开契约镜像并用一次最小验证批次收敛功能 055。

- [x] T019 在 `04-demo/tools/demo-api-mirror/api.mts`、`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 和 `04-demo/frontend/tests/apiCompatibility.test.mjs` 同步线路落位、v2 节点及梁场部署字段，只更新功能 055 涉及的冻结契约并保护现有无关基线改动。
- [x] T020 按 `03-requirements/specs/055-girder-dual-carriageway-topology/quickstart.md` 运行项目主数据/线路图/方案兼容目标 pytest、`04-demo/frontend/tests/girderPlanSimulation.test.mjs`、TypeScript 类型检查和前端构建各一次，记录实际命令、退出码及未覆盖的源 Excel 精确导入风险。

---

## 依赖与执行顺序

- T001～T005 建立共享项目主数据契约和持久化，阻塞所有用户故事。
- US1 按 T006/T007（先写测试）→ T008/T009 → T010 执行。
- US2 依赖 US1 的 v2 节点契约，按 T011/T012（先写测试）→ T013/T014 执行。
- US3 依赖 US1/US2 的稳定节点与诊断，按 T015/T016（先写测试）→ T017/T018 执行。
- T019 依赖共享契约和三个故事完成；T020 最后执行且不重复全仓验证。

### 可并行任务

- T001 与 T002 修改不同测试边界，可并行准备；实现仍由 T003→T004/T005 收敛。
- T006 与 T007、T011 与 T012、T015 与 T016 分属后端/前端或不同测试文件，可并行编写失败测试。
- 不并行修改 `topology.py` 的 T009 与 T013，也不并行修改共享契约的 T008 与 T017。

## 一致性覆盖

| 来源 | 覆盖任务 |
| --- | --- |
| US1 / FR-001～FR-007 / SC-001、SC-002、SC-004 | T001～T010 |
| US2 / FR-005、FR-008～FR-010 / SC-003、SC-005 | T011～T014 |
| US3 / FR-012、FR-014～FR-016 / SC-006 | T015～T018 |
| FR-011、FR-013 共享显示与契约 | T008、T010、T019 |
| SC-007 性能与完整收敛 | T020，并沿用功能 051 现有性能样例 |
| 计划决策：新增落位实体和 schema v2 | T001～T005 |
| 计划决策：v2 指纹、稳定桥梁目标、梁场节点定位 | T008、T015～T018 |
| 计划决策：后端/前端/API/演示镜像一致 | T003、T008、T017、T019 |

**一致性结论**：全部可实施 FR、SC、用户故事验收项和计划决策均至少映射到一个任务；没有超出 `plan.md` 的路径、重复全套验证或尚未解决的业务口径。
