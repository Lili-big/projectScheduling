# 任务清单：连续结构桥梁分段与线路图清晰展示

**输入**：来自 `03-requirements/specs/058-girder-continuous-bridge-segments/` 的规格、计划、研究、数据模型、契约和快速验收指南

**前置条件**：用户确认本清单后，才可执行 `$speckit-implement`。

## Phase 1：用户故事 1 - 按真实结构识别三段式桥梁路线（P1）

**目标**：证据完整的连续结构桥梁每幅形成三个里程连续的路线节点；两个引桥段分别成为待架目标，连续结构段自动进入通路和交付控制。

**独立测试**：用 `K1000+000～K1000+800` 的 200m 简支＋300m 连续＋300m 简支样例验证节点、梁片需求、相邻边和展开路线。

- [x] T001 [US1] 先在 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 和 `04-demo/backend/tests/test_girder_plan_simulation_validation.py` 增加 v3 正常三段、左右幅独立段界、分段梁片汇总及“两个引桥目标自动展开包含连续段”的失败测试
- [x] T002 [US1] 在 `04-demo/backend/app/contracts/girder_plan_simulation.py` 和 `04-demo/frontend/src/contracts/girderPlanSimulation.ts` 同步增加可空 `bridge_segment_kind` 枚举并把线路图契约升级为 `girder-plan-line-graph/v3`
- [x] T003 [US1] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 实现按 `span_index → sort_order → structure_id` 排序、识别相邻 `continuous_unit` 区块、按结构长度累计三段里程及稳定分段节点 ID 的派生逻辑
- [x] T004 [US1] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 将梁型需求、源引用和当前计划完成日期限定到所属区段，并让 `build_line_graph` 接收一个落位的多个节点、按真实里程生成区段内部和相邻工点边、将 v3 分段内容计入指纹

**检查点**：后端正常样例恰好生成三段，人工目标只有两个引桥段，路径展开包含连续段；非连续桥梁仍为一个原 ID 节点。

---

## Phase 2：用户故事 2 - 在密集线路图中直接看清工点（P2）

**目标**：完整名称在两条错位轨道上直接可读；桥隧只用粗线段表达，左右幅和 K 里程关系不变。

**独立测试**：泸古 1 标密集双幅案例中无名称省略号、桥隧圆形 marker 为零、三段在父空间组内按相对里程显示。

- [x] T005 [P] [US2] 先在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 更新线路图旅程断言，覆盖完整名称、双行错位标签、桥隧无圆形 marker、线段图例和三段相对里程定位
- [x] T006 [US2] 在 `04-demo/frontend/src/features/girderPlanSimulation/LineGraphView.tsx` 将节点名称改为可点击的完整文本标签，按稳定顺序交替两行，并在同一 `spatial_group_id` 内按每幅节点起终里程计算标签中心和粗线段位置；桥梁、隧道不再渲染圆形轨道图标
- [x] T007 [US2] 在 `04-demo/frontend/src/features/girderPlanSimulation/styles.css` 实现两条名称轨道、可见溢出/允许重叠、不中断对象聚焦的点击层及桥隧线段式图例，同时保持现有双幅高度和路基压缩比例

**检查点**：用户无需悬停即可识别所有工点；名称可重叠但不裁切，桥梁/隧道只保留粗线段且仍可点击、显示风险和里程。

---

## Phase 3：用户故事 3 - 安全处理旧方案和不完整数据（P3）

**目标**：无法唯一拆三段的数据阻断计算并可定位；旧整桥方案失效而不猜测迁移；演示镜像与正式 API 行为一致。

**独立测试**：覆盖五类阻断数据和一个旧整桥目标方案，验证诊断 code/subject/source refs、blocking 状态及 v2 成果失效。

- [x] T008 [US3] 先在 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 增加缺结构顺序/长度、多个不相邻连续区块、零长度引桥、总长超 1m、连续段含预制梁五类阻断测试，并在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 增加 v3 契约与旧整桥目标不可复用测试
- [x] T009 [US3] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 实现 `BRIDGE_SEGMENT_STRUCTURE_DATA_MISSING`、`BRIDGE_SEGMENT_CONTINUOUS_BLOCK_AMBIGUOUS`、`BRIDGE_SEGMENT_APPROACH_MISSING`、`BRIDGE_SEGMENT_LENGTH_MISMATCH`、`BRIDGE_SEGMENT_PRECAST_CONFLICT` 对象级诊断；异常时保留定位节点但使快照 blocking
- [x] T010 [US3] 在 `04-demo/backend/app/girder_plan_simulation/service.py` 和 `04-demo/backend/app/girder_plan_simulation/validation.py` 验证并仅在测试暴露缺口时收紧现有 `LINE_GRAPH_CHANGED`、`ROUTE_TARGET_INVALID`、stale/指纹路径，确保旧整桥目标不自动映射为两个引桥目标
- [x] T011 [US3] 在 `04-demo/tools/demo-api-mirror/api.mts` 输出 v3 契约和至少一组“小里程引桥—连续结构—大里程引桥”镜像节点，使静态页面、待架目标和路径展开与后端一致

**检查点**：五类异常均阻断且有源证据；普通桥梁 ID 不变；旧整桥成果历史可读但不能作为 v3 当前成果确认。

---

## Phase 4：收敛验证

- [x] T012 [P] 按共享字段实际差异更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json` 和 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`，并通过 `04-demo/backend/scripts/capture_architecture_baseline.py` 与 `04-demo/frontend/scripts/captureArchitectureBaseline.mjs` 的 check 模式确认无未解释契约漂移
- [x] T013 按 `03-requirements/specs/058-girder-continuous-bridge-segments/quickstart.md` 只运行一次目标后端 pytest、前端 `node:test` 和 `npm.cmd run typecheck`，记录各命令退出结果并确认独立成果边界文案仍存在
- [x] T014 使用 `03-requirements/specs/058-girder-continuous-bridge-segments/quickstart.md` 的泸古 1 标页面清单做一次默认缩放视觉验收，核对全名双行、桥隧无圆点、三段里程、左右幅对应和对象聚焦；只在发现本功能缺陷时修复并重跑对应最小验证

## 依赖与执行顺序

- T001 → T002 → T003 → T004：先固定 v3 正常行为，再实现共享契约和三段投影。
- T005 → T006 → T007：前端测试先行；依赖 T002 的前端类型，但不依赖 US3 诊断。
- T008 → T009 → T010：异常和兼容测试先行；T010 仅处理测试证明存在的服务/校验缺口。
- T011 依赖 T002、T004，可与 T008～T010 在不同文件上并行。
- T012 依赖所有共享契约修改；T013 依赖 T001～T012；T014 依赖 T013。
- 唯一明确并行项：T005 可与后端 T003/T004 并行，T011 可与 T008～T010 并行；不得并行编辑同一个 `topology.py` 或同一个测试文件。

## 一致性覆盖

| 来源 | 覆盖任务 |
| --- | --- |
| US1；FR-006～FR-014；SC-003～SC-004 | T001～T004、T013 |
| US2；FR-001～FR-005；SC-001～SC-002 | T005～T007、T014 |
| US3；FR-015～FR-017；SC-005～SC-006 | T008～T012、T013 |
| FR-018 独立成果边界 | T013 |
| OpenAPI v3、前后端字段、演示镜像一致 | T002、T011～T013 |
| 五类失败关闭与旧方案失效 | T008～T010、T013 |

**一致性结论**：全部可实施 FR、SC、用户故事验收项和计划决策均有任务覆盖；没有无来源任务、重复全量验证、持久化迁移或计划外路径。
