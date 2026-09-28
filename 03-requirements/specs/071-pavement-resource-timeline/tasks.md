# 实施任务：路面单机时间图与沥青恢复

状态：用户最新批注明确要求在机组施工顺序前增加资源时间图，授权实施资源图部分；本轮核心任务与证据已完成。累计8/9完成（T001/T002、T003/T004/T005a/T006/T007/T008）；原T005拆分为接入图表与底部精简，唯一未完成T005b不在本轮范围。

输入：[spec.md](./spec.md)、[plan.md](./plan.md)、[data-model.md](./data-model.md)、[契约](./contracts/resource-timeline.md)、[验证指南](./quickstart.md)。

## US3：允许未知厚度的长度排程

- [x] T001 [US3] 修改 `04-demo/backend/app/project_master/validation.py` 的共享数量校验：m计量跳过厚度计算校验，其他计量方式继续原规则；几何m仍核对净长与数量；其他单位、资源与移交规则保留。
- [x] T002 [US3] 在 `04-demo/backend/tests/test_pavement_master.py`、`test_pavement_generation.py`、`test_pavement_layer_template.py`、`test_pavement_solver.py`、`test_pavement_api.py`（均位于 `04-demo/backend/tests/`）更新受影响断言并补充空厚度/非法厚度/几何量、FS+7、1001m工期2天及零机组失败样例；运行quickstart第1项一次，证明生成和直接/场景求解同口径。

## US1：单机作业与空闲

- [x] T003 [US1] 扩展 `04-demo/frontend/src/features/scheduleResults/pavementViewModel.ts`，生成真实资源行、作业/转场/空闲片、首末作业期、并集统计和最长空闲；处理零任务、多实例、重叠、缺失转场、无效边界及历史数据，不改原对象。
- [x] T004 [US1] 新增 `04-demo/frontend/src/features/scheduleResults/PavementResourceTimeline.tsx` 并扩展同目录 `styles.css`：每套资源一行、共享日期轴、筛选、统计、可键盘访问的区间详情和最长空闲定位；窄屏内部滚动，同次快照更新后保持有效选择。

## US2：接入新图与精简结果

- [x] T005a [US1] 修改 `04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`，在计划图与机组施工顺序间接入资源时间图；沿用可行结果显示门槛和同次快照。
- [ ] T005b [US2，暂缓] 移除 `04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx` 输入来源和计算耗时details；修改 `04-demo/frontend/src/app/Workspace.tsx` 仅路面分支，将底部完整诊断块移除、错误移至求解区alert，修正无方案指引，保留任务页、桥梁、顶部进度及移交前提；相应补充底部精简与错误承接的测试和页面验收。本轮未修改这些展示块。
- [x] T006 [US1] 扩展 `04-demo/frontend/tests/pavementVisualization.test.mjs` 和 `04-demo/frontend/tests/pavementResults.test.mjs`，验证SC-001精确数值、多资源、期外不算空闲、缺失/无效数据降级、同次更新及组件顺序；运行quickstart第2项一次。底部精简验证随T005b执行。

## 联合验收与证据

- [x] T007 执行 `package.json` 的build命令；按 `03-requirements/specs/071-pavement-resource-timeline/quickstart.md` 第4/5项使用当前19段76任务的有限预算结果验证资源图、筛选、区间详情、键盘、最长空闲及宽窄屏；样例测试覆盖多资源、无任务和异常信息。截图及核验放 `.local-data/logs/<本次时间>-pavement-resource-timeline/`，不改真实机组数量或启停。厚度与历史95任务/FS+7验收复用T001/T002证据，底部错误承接随T005b验收。
- [x] T008 将实际变更、命令退出码、页面证据、非阻塞失败与剩余限制写入 `03-requirements/specs/071-pavement-resource-timeline/tasks.md`；按事实更新同目录spec/plan状态、`03-requirements/specs/README.md`、`agent.md`、`04-demo/README.md`，执行quickstart第6项仓库/生命周期/文档检查，新增问题修复、既有问题留证。

## 已完成的直接授权操作（不重复执行）

- V32→V51：在用19段各追加一层启用沥青，95个启用层；未知厚度/密度留空；旧层和6段停用范围保持，API回读通过。
- 用户补充后已保存：上水稳→沥青FS+7，沥青转场1天，工效1000m/天原值回读确认；资源数量/上限/启停未改。
- 证据：`.local-data/logs/20260927-210701-restore-asphalt/master-before.json`、`master-after.json`、`verification.json`、`config-before.json`、`scenario-config-after.json`。T001完成后已验证95个任务及19条FS+7，厚度错误已消失；实际机组未投入仍报资源不足，不能宣称真实95任务已求解。

## 依赖与数量

总计9项：US1四项（T003/T004/T005a/T006），US2一项（T005b），US3两项（T001/T002），联合验收两项（T007/T008）。资源图按T003→T004→T005a→T006→T007→T008实施；T005b独立暂缓。本轮不需要子代理或重复独立审查，未标P。

## 一致性检查（2026-09-27）

| 需求/验收/决策 | 对应任务或直接证据 |
|---|---|
| FR-001/002，US1-1，SC-002/003，D2/D3 | T003/T004/T006/T007 |
| FR-003/004/005，US1-3，SC-001，D2 | T003/T006 |
| FR-006，US1-2，D3 | T003/T004/T006/T007 |
| FR-008，US1-4及全部图形边界，D2/D3 | T003/T004/T006/T007 |
| FR-002资源图接入 | T005a/T006/T007 |
| FR-007，US2全部，SC-004，D4 | T005b（含相应测试、验收，暂缓） |
| FR-009，US3恢复与参数，D1 | 本文直接证据＋T002/T007 |
| FR-010，US3长度排程，SC-005/006，D1 | T001/T002/T007 |
| 保留未提交修改、合法归属、完成证据 | T007/T008 |

结果：需求、验收、数据模型和契约一致，覆盖缺口0；任务均有来源和精确路径，无重复全量验证。所有新代码任务在原计划边界内。厚度校验已获用户直接授权并完成；最新明确批注授权资源横道图T003/T004/T005a/T006及对应T007/T008验收，本轮不重开规划或确认。底部精简T005b另列待办，不冒充完成。机组数量由用户自管，不再作为待澄清项。

## 历史规划阶段验证

- validate_docs.py：退出0，14份文档链接/API事实通过。
- validate_repository.py：退出1，既有requirements.txt架构依赖审批缺失，与本轮未改依赖无关。
- validate_lifecycle_workspace.py：退出1，仍为此前9处历史工作包输入/成果引用缺失；没有071路径违规。上述两项不阻塞本轮规划确认，不扩大修复范围。
- 新代码尚未实施，未运行功能测试/构建；完成状态仍为0/8。


## T001/T002实施证据（2026-09-27）

- 用户批注是本轮厚度约束任务的明确执行指令，无需重复确认。本次仅修改后端共用校验与邻近测试；未实施新图表/底部精简。
- 改动：validation.py在m计量的数量校验与待移交校验均跳过厚度，几何净长比较仍执行。m2/m3/t保留厚度约束；表单保存正数校验未调整。
- 修改测试：test_pavement_master.py、test_pavement_generation.py、test_pavement_layer_template.py、test_pavement_api.py；test_pavement_solver.py随相关套件回归。
- 按quickstart第1项首轮86通过、1失败，失败为新增用例错误调用既有测试helper；改为直接构造PavementDependencyRule后仅重跑该项，1通过。合计87个相关用例通过。
- 新服务已按runtime脚本启动并通过health；真实API生成19段95任务、19条FS+7关系，沥青工期为ceil(长度/1000)，厚度仍为空且不再报错。沥青机组仍停用/0套，资源不足是用户自管配置事实，未改变。
- 证据目录：.local-data/logs/20260927-212543-length-without-thickness/，含generated.json、verification.json、state-before.json及页面证据。
- 本轮纯后端定向修改，不重复前端构建/未实施图表测试。规格和宪章术语按最新用户要求同步；计划阶段既有仓库检查失败保持前述分类。
- 页面已重新执行校验：无thickness_m错误，实际仅资源不足；截图 `after-validation.png`。主数据与配置前后SHA256一致。validate_docs.py退出0（14份文档）；本轮未修改用户数据。

## 资源时间图实施证据（2026-09-27）

- 执行范围：最新用户批注明确授权资源行/时间轴横道图及其位置。T003/T004/T005a/T006/T007/T008完成；T005b底部精简未执行，保留原有错误和诊断展示。未修改求解器、共享接口、持久化结构、主数据、机组数量、工效或保存配置。
- 实现路径：`04-demo/frontend/src/features/scheduleResults/pavementViewModel.ts`新增资源时间投影；`PavementResourceTimeline.tsx`新增图与交互；`ScheduleResultsWorkspace.tsx`接入；同目录`styles.css`提供布局及图例。真实实例逐行显示，启用但无任务的实例显示空态；作业/转场取并集，作业期外不计空闲，养生不直接占用资源，异常和缺转场时降级为信息不足；只使用同次结果/生成输入，稳定key支持新方案更新。
- 测试路径：`04-demo/frontend/tests/pavementVisualization.test.mjs`与`pavementResults.test.mjs`。命令 `node --test 04-demo/frontend/tests/pavementVisualization.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs` 退出0，21通过/0失败；含SC-001的5/1/2天及62.5%、多实例、空资源、未分配任务、重复转场、边界/重叠/缺失、快照更新、不变输入及组件顺序。无方案不出现资源行。
- `npm.cmd run build` 首次退出0；浏览器发现全局button的34px固定高度挤掉资源名，局部设置资源名单元格100%高度和正确层叠后，仅重跑受影响构建，退出0。TypeScript及Vite通过；既有大于500kB分包建议仍存在，不阻塞本图。
- 页面验收使用独立标签页及原保存配置（2026-09-23开工），有限预算求解；用户原标签页的2026-09-01未保存输入保持。当前19段76任务、单套碎石/水稳共享机组，分析期2026-09-23至2027-06-05共256天：作业196天、转场56天、期间空闲4天、最长空闲1天、期间作业率76.6%。三者之和256天；图位于任务计划图之后、机组施工顺序之前。
- 实际交互：资源筛选选中真实实例；键盘Enter选择转场显示2026-09-27及前后任务；“定位最长空闲”聚焦2027-05-24的1天空档，显示05段左幅水稳下基层与11段右幅水稳下基层作为前后作业。只展示空闲事实，不自动归因窝工。
- 宽屏1280px与窄屏640px页面宽度分别保持1280/640；窄屏图内1120px内容在598px容器滚动，最长空闲定位后焦点仍在目标区间；资源名高度16px可读。临时视口已恢复。多资源及异常快照由固定样例测试覆盖，真实页面仅有1套资源。
- 证据：`.local-data/logs/20260927-223850-pavement-resource-timeline/browser-verification.json`、`resource-timeline-wide.png`、`resource-timeline-narrow.png`及三份验证日志。
- 仓库要求的检查各运行一次：`validate_docs.py`退出0（14份文档链接/API事实通过）；`validate_repository.py`退出1，仍为既有requirements.txt架构依赖审批缺失；`validate_lifecycle_workspace.py`退出1，仍为9处历史工作包输入/成果引用不存在。两项失败与本次未改依赖、未移动历史资产无关，无新增071/图表路径违规，不影响资源图核心验收，未扩展修复。命令日志在上述证据目录。
- 限制：资源粒度为当前排程的一套机组，不能推断其内部每台机械；期间作业率不是设备台班利用率。真实单机验收及合成多机/异常测试已覆盖本次目标，底部精简仍是独立待办。
