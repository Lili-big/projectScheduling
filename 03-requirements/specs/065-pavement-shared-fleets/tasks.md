# 实施任务：路面机组跨工艺共享

**状态**：用户已确认并实施完成；10/10。实际命令、API回读及浏览器验收见quickstart.md。  
**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[接口契约](./contracts/shared-fleets.md)、[quickstart.md](./quickstart.md)。

## US1：可配置并持久保存共享能力

- [x] T001 [US1] 在 `04-demo/backend/tests/test_pavement_contracts.py`、`04-demo/backend/tests/test_pavement_config.py` 先补充共享字段回读、桥梁缺省序列化不变、旧专用能力回退、新保存空能力拒绝、其他项目不变和非法引用测试；记录实施前缺失行为。
- [x] T002 [US1] 在 `04-demo/backend/app/contracts/_models.py` 为Resource添加可选compatible_process_ids，在 `04-demo/backend/app/contracts/pavement.py` 为PavementTaskContext添加可选process_id；同步 `04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/frontend/src/contracts/pavement.ts`，缺省省略新字段，不改变桥梁合同。
- [x] T003 [US1] 在 `04-demo/backend/app/scheduling/domain/resource_scope.py` 增加路面专用能力解析/匹配及校验辅助函数；在 `04-demo/backend/app/local_scenario_config.py` 接入旧专用池加载规范化和新保存严格校验，明确通用类型、有效数量、空能力、未知引用、名称、数量、ID、转场及工点规则；复用已有保存API，不改桥梁分支。
- [x] T004 [US1] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx`、`04-demo/frontend/src/features/resources/styles.css` 和 `04-demo/frontend/src/domain/pavement.ts` 实现机组名称、工艺多选、新增/停用与现有数量/转场/工点配置；新增组0套、无预设转场，保存中禁用编辑、失败保留输入，空态有新增入口；在 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 覆盖能力编辑、空能力校验、共享数量不翻倍和所有资源字段使结果失效。

独立验收：同一机组勾选碎石、水稳，保存并刷新仍为1套；旧项目读取维持专用含义。实施源码修改到此尚不能声称求解支持共享。

## US2：跨工艺分配保持真实容量

- [x] T005 [US2] 在 `04-demo/backend/tests/test_pavement_generation.py`、`04-demo/backend/tests/test_pavement_solver.py`、`04-demo/backend/tests/test_pavement_api.py` 先添加quickstart核心场景：1套/2套共享的2天/1天工期、跨段1天转场、原位换工艺、养生释放、专用与共享并存、工点限制、0套忽略未填转场、非法能力、直接求解及旧负载兼容；现有不足证据先记录。
- [x] T006 [US2] 在 `04-demo/backend/app/scheduling/generation/pavement.py` 给任务写入实际工艺ID，并通过有效池来源映射给资源实例附加能力；每池仅按数量展开一次，候选按能力及范围判断；消除“三类必须专用”限制，对实际0可用实例不强求转场，保留真实缺资源和非法输入诊断。
- [x] T007 [US2] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 使用T003匹配函数并校验直接请求；对显式能力优先精确匹配，对旧专用资源保留单类回退，对新能力配旧任务缺process_id提示重新生成；复用 `04-demo/backend/app/scheduling/solver/constraints/pavement.py` 的每实例单路径/NoOverlap，保持资源固定约束、转场、养生、工期及目标。
- [x] T008 [US2] 在 `04-demo/frontend/tests/pavementResults.test.mjs` 验证同一实例跨工艺任务仍只归属一套机组，转场和名称正确；仅在发现实际显示问题时修正 `04-demo/frontend/src/features/scheduleResults/presenter.ts`。以 `04-demo/backend/tests/test_pavement_api.py` 和 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 覆盖接口字段、旧桥梁合同及演示镜像拒绝路面；只在漏识别新字段时更新 `04-demo/tools/demo-api-mirror/api.mts`。

独立验收：完整样例求解证明跨工艺单机互斥、双机并行与转场一致；客户其他配置缺项不通过自动填造解决。

## 验证与客户配置应用

- [x] T009 按 `03-requirements/specs/065-pavement-shared-fleets/quickstart.md` 运行一次相关pytest、node:test（含 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs`）和构建；仅修复本功能相关失败并针对性复测，记录命令、退出结果及非核心既有问题。
- [x] T010 [US1] 自动验证通过后按 `04-demo/runtime/README.md` 更新运行服务；重新GET并备份现有配置，通过既有API仅更新pavement-project的水稳池为碎石/水稳共享1套，保留1天转场及其他配置；写入前重新核对避免覆盖期间编辑。浏览器检查未保存状态后刷新核对编辑、保存、数量与名称，记录API回读差异及其他阻塞，更新 `03-requirements/specs/065-pavement-shared-fleets/quickstart.md`、本文件及 `03-requirements/specs/README.md` 的实际完成状态。

## 执行依赖

串行T001→T002→T003→T004→T005→T006→T007→T008→T009→T010；不使用子代理。US1为5项（含客户应用T010），US2为4项，共享验证1项。全部通过前不得只因界面可多选就宣称共享求解完成。

064路床三态独立待确认，无实施依赖；本次禁止顺带修改其状态/规则。养生条件合并为可用节点仅是上一轮建议，未纳入此任务。

## 一致性检查（2026-09-24）

| 覆盖来源 | 实施/证据 |
| --- | --- |
| FR-001；US1场景1—3 | T001—T004、T010 |
| FR-002—FR-004；US2场景1、2、4 | T005—T007 |
| FR-005、FR-006；US2场景2、3 | T005—T007，复用既有求解约束 |
| FR-007；US1场景4、US2场景5 | T001—T004、T007—T010 |
| FR-008；边界、错误、兼容 | T001、T003—T009 |
| FR-009；US2场景5 | T008、T010 |
| FR-010 | T010 |
| SC-001、SC-005 | T001、T004、T006、T010 |
| SC-002—SC-004 | T005—T009 |
| D1—D5 | T001—T004、T006、T007 |
| D6—D8 | T003—T009 |
| D9、D10 | T009、T010；064及养生重构明确排除 |

检查结果：10个唯一任务ID；FR、SC、两故事全部验收及D1—D10有对应任务。无悬空需求、无无来源任务，无先用后建的依赖，无重复全量测试，路径均在plan范围或既有运行/状态归属内。上述为实施前检查结论。用户随后已确认实施，当前10项均完成；实际实现和客户配置更新证据见quickstart.md。
