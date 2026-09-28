# 实施任务：路面排程结果与机组线路可视化

**状态**：用户已“确认执行”；15/15完成，核心验证通过。  
**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[交互契约](./contracts/results-ui.md)、[quickstart.md](./quickstart.md)。  
**范围**：只改路面前端展示与请求内展示状态；保持069算法、HTTP协议、预算、机组、工效、主数据及保存配置。

## US1：明确感知持续求解并读懂计划前提

独立验收：无改善时仍有活动和计时，终态停止；摘要精简、移交日期含义准确，历史/失败不出现假日期。

- [x] T001 [US1] 在`04-demo/frontend/tests/pavementLiveSolve.test.mjs`补充started预算保留、终态/中断及旧token不影响新状态用例；在`04-demo/frontend/tests/pavementResults.test.mjs`补充状态/范围合并、当前最好与最终、待移交新列名及缺字段/失败兼容断言，先确认新行为缺失。
- [x] T002 [US1] 在`04-demo/frontend/src/app/workflows/solveWorkflow.ts`将已校验started.time_budget_seconds保留到内部PavementLiveState，未知用null，沿用elapsed及既有单调方案、取消、序号和错误处理；不改事件协议。
- [x] T003 [US1] 新增`04-demo/frontend/src/features/scheduleResults/PavementSolveProgress.tsx`，并修改`04-demo/frontend/src/app/Workspace.tsx`记录与token绑定的单调时钟开始时刻、传递live状态及同次solved.generated；实现无首解/持续优化/等待收尾提示、本地已等待计时和终态/中断/卸载清理，保持输入变更隔离。
- [x] T004 [US1] 修改`04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`及`04-demo/frontend/src/features/scheduleResults/styles.css`，接入活动提示，合并状态/范围摘要，使用“本方案最晚需移交日”及后置安排/当天开工前移交说明；保留无方案、历史blocked、初解保留、真实最优性及计算详情。

## US2：两级表格、横道、工艺关系与等待

独立验收：每个任务唯一对应子级，父级不画施工条；真实关系端点与等待区间准确，左右行对齐，折叠不伪造关系。

- [x] T005 [US2] 新增`04-demo/frontend/tests/pavementVisualization.test.mjs`的合成结果样例与投影测试，覆盖两级唯一任务、同类多层/配套、四类关系及正/零/负间隔、等待唯一/歧义/附加等待、缺generated、日期边界和输入不可变；按quickstart预期确认缺失行为。
- [x] T006 [US2] 新增`04-demo/frontend/src/features/scheduleResults/pavementViewModel.ts`，实现基于同次result/generated的稳定施工段分组、工序行、真实关系端点、等待归属和日历坐标投影，缺失/不一致只降级相应图形；不读取当前scenario，不修改输入。
- [x] T007 [US2] 新增`04-demo/frontend/src/features/scheduleResults/PavementPlanTimeline.tsx`，实现共同行左表右横道、日历刻度、父级折叠/全展开/全收起、子级施工条、真实关系开关与入出边高亮、等待虚线及按需详情；折叠端点不接到父级，提供键盘可达控件。
- [x] T008 [US2] 在`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`替换平铺任务表和等待长列表，接入本次generated及新表图；在`04-demo/frontend/src/features/scheduleResults/styles.css`实现冻结列、同高行、内部滚动、图例和宽窄屏布局；适配`04-demo/frontend/tests/pavementResults.test.mjs`的组件加载及层级/空态/未定位等待静态断言。

## US3：机组里程轴与实际施工顺序

独立验收：机组任务全部可追溯，施工顺序不被里程排序替代；连续同段合并、返回保留，混合桩号降级，转场事实准确。

- [x] T009 [US3] 扩展`04-demo/frontend/tests/pavementVisualization.test.mjs`，覆盖A→A→B→A、逆里程、左右幅/工点/桩号系列分轴、跨轴前后关系、同桩号/重叠、缺失/非法/混合桩号和坐标冲突、未分配/重叠异常任务、实际/零天/未知转场；检查每个已分配任务恰好归属一次到访。
- [x] T010 [US3] 在`04-demo/frontend/src/features/scheduleResults/pavementViewModel.ts`增加机组时间排序、连续位置到访、稳定key/全局序号、严格桩号解析、按工点/系列/幅别分轴及不可定位区；精确匹配相邻转场，不根据空档算转场、不推算地理距离。
- [x] T011 [US3] 新增`04-demo/frontend/src/features/scheduleResults/PavementCrewRoute.tsx`，提供机组选择、带桩号刻度的比例轴、到访序号/区间、选中前后相邻方向连接、跨轴文本跳转、上一步/下一步、工序及转场详情；重复位置逐行显示，无法定位到访同样可导航。
- [x] T012 [US3] 在`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`用机组轴替换路线长串及全部转场列表，在`04-demo/frontend/src/features/scheduleResults/styles.css`补充轴线/选中/空态样式，在`04-demo/frontend/tests/pavementResults.test.mjs`补充相关渲染断言；新方案按稳定ID保持有效折叠/机组/到访选择并清理失效详情。

## 集成验证与完成证据

- [x] T013 按`03-requirements/specs/070-pavement-results-visualization/quickstart.md`运行三个目标前端测试文件及一次npm run build（含tsc），修复本轮相关失败；在`03-requirements/specs/070-pavement-results-visualization/tasks.md`记录命令和实际退出结果，不重复未受影响的后端全量测试。
- [x] T014 按`03-requirements/specs/070-pavement-results-visualization/quickstart.md`在原有8000页完成一次有限预算实时结果验收及宽/窄视口交互、历史/键盘/减少动画检查；用`.local-data/logs/20260927-193733-pavement-live/http-final.json`核对100任务投影，在`.local-data/logs/<本次时间>-pavement-visualization/`保存截图及数据未持久化变更证据，真实未覆盖项写入本目录tasks.md。
- [x] T015 在`03-requirements/specs/070-pavement-results-visualization/spec.md`、`03-requirements/specs/070-pavement-results-visualization/plan.md`、`03-requirements/specs/070-pavement-results-visualization/tasks.md`、`03-requirements/specs/README.md`、`agent.md`和`04-demo/README.md`按实测更新完成状态与操作说明；若新增/调整资产再次按quickstart检查归属，仅记录既有非核心失败，不修无关历史问题。

## 依赖与执行顺序

- US1：T001→T002→T003→T004，形成可单独阅读和验证的第一批价值。
- US2：T005→T006→T007→T008；集成时复用T003的同次generated传递。
- US3：T009→T010→T011→T012；T010在T006建立的局部投影文件上扩展。
- 收尾：T013→T014→T015，依赖三故事完成。
- 共15任务：US1 4、US2 4、US3 4、跨故事3。多个任务共享投影、容器、样式与测试文件，本次按顺序实施，不标并行任务，不分配子代理。
- 测试任务先准备断言和最小样例；实现后统一执行相关批次，失败才补查，不重复全套测试。

## 一次性一致性检查

规格、设计、数据映射与UI契约已逐项交叉核对。所有建设项均在plan允许路径内；没有无来源任务、重复全量验证或新增业务规则。覆盖如下：

| 需求 | 用户故事验收 | 成功标准 | 对应任务 |
| --- | --- | --- | --- |
| FR-001 | US1.1、US1.2、US1.3 | SC-001 | T001–T004、T013–T014 |
| FR-002 | US1.2、US1.4 | SC-001、SC-005 | T001–T004、T014 |
| FR-003 | US1.4、US1.5 | SC-005 | T001、T004、T014 |
| FR-004 | US2.1 | SC-002 | T005–T008、T014 |
| FR-005 | US2.2 | SC-002、SC-006 | T006–T008、T014 |
| FR-006 | US2.3 | SC-003 | T005–T008、T014 |
| FR-007 | US2.4、US2.5 | SC-003 | T005–T008、T014 |
| FR-008 | US3.1、US3.4 | SC-004 | T009–T012、T014 |
| FR-009 | US3.2、US3.3 | SC-004 | T009–T012、T014 |
| FR-010 | US3.1、US3.3、US3.5 | SC-004 | T009–T012、T014 |
| FR-011 | US1.3、US1.5；异常/历史 | SC-005、SC-006 | T001–T006、T008、T012–T014 |
| FR-012 | 新方案更新边界 | SC-006 | T003、T006–T008、T010–T014 |
| FR-013 | US2.2、US3.3；宽窄屏/可用性 | SC-006 | T003–T004、T007–T008、T011–T014 |
| FR-014 | 范围和不可变边界 | SC-003、SC-006 | T005、T006、T009、T010、T013–T015 |

设计覆盖：D1→T003/T006/T008/T012；D2→T001–T004；D3→T001/T004；D4→T005–T008；D5→T005–T008；D6→T009–T012；D7→T001/T008/T012–T015。research的八项结论均归入D1–D6，data-model字段来源及缺省对应投影/状态测试，UI契约的状态、顺序、交互及兼容对应上述三故事。

**检查结论**：14项FR、6项SC、15个故事验收场景及7项设计决策全部覆盖；覆盖缺口0，阻塞澄清0。该结论为规划一致性通过，不是应用验证通过。用户已确认本清单及一致性结果，已执行speckit-implement。

## 规划阶段资产检查

2026-09-27已运行：

- `.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py`：退出1，仅报告既有`requirements.txt changed without architecture dependency approval`，本轮未改依赖。
- `.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py`：退出1，9处既有missing-workpackage-reference（历史客户验证材料7处、standalone/json-task-viewer的input/output各1处），warnings为0；输出未涉及070新增规格路径。
- 以上结果与前序已知失败一致，不扩大本轮修复范围。规划文档完成不代表这些仓库检查全通过，也不代表15项应用任务完成。

## 实施证据

实施已完成，实际证据如下。

### 实际修改

- 新增局部前端文件：pavementViewModel.ts、PavementSolveProgress.tsx、PavementPlanTimeline.tsx、PavementCrewRoute.tsx，均在04-demo/frontend/src/features/scheduleResults/。
- 修改同目录presenter.ts、ScheduleResultsWorkspace.tsx、styles.css，以及src/app/Workspace.tsx、src/app/workflows/solveWorkflow.ts；修改两份既有测试并新增pavementVisualization.test.mjs。
- Workspace相对本轮开始备份的diff仅为进度状态、计时、generated传递和组件接入；未修改后端、HTTP契约、算法、依赖、客户输入或保存结构。
- 本轮开始前的五个相关源文件备份保存在证据目录，保护前序未提交改动；未提交或重置工作树。

### 自动验证（2026-09-27）

证据目录：`.local-data/logs/20260927-200911-pavement-visualization/`。

1. 先运行新增预算/移交断言，2项预期失败，证实旧行为缺失；表图投影模块缺失和路线函数缺失也按测试先行确认，随后实施。
2. `node --test --test-concurrency=1 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementLiveSolve.test.mjs 04-demo/frontend/tests/pavementVisualization.test.mjs`：19项通过，退出0。
3. 初次`npm run build`发现generated可选时访问workpoint_name缺少空值收窄，已修正。同次补充表图/里程轴静态断言后，两个受影响测试文件14项通过；build退出0。
4. 窄屏布局及到访自动定位完善后，仅重跑受影响的pavementResults.test.mjs，8项通过；再次build退出0。Vite仍有既有超过500kB的bundle提示，不影响构建。
5. 补充可控时钟用例，运行`node --test --test-name-pattern='progress keeps ticking' 04-demo/frontend/tests/pavementResults.test.mjs`，1项通过，退出0：同一方案0次改善下已等待从5秒到10秒持续递增，complete/interrupted/unmount均清理计时器。另补充多机组到访/转场隔离用例，使用multiple fleets名称过滤定向运行1项通过；全部现有目标用例合计21项已通过，未无故重复未受影响测试。
6. `node .local-data/logs/20260927-200911-pavement-visualization/verify-snapshot.mjs`：退出0。辅助脚本首次相对路径多写一层导致模块找不到，已修正脚本路径，不涉及应用。真实069快照验证25父级、100任务、75关系、50等待、0未定位等待；76次到访、8轴、3次无法统一定位到访；100个已分配任务全部恰好出现一次，源对象不变。详见snapshot-check.json。该历史快照与本轮并行求解的75次到访不同，展示以各自真实方案为准。
7. project-master.db、scheduler-config.json的前后SHA256完全相同，见state-before.json与state-after.json。

### 页面验收

- 原绑定的浏览器标签在当前工具会话中已失效，确认同一浏览器无可用标签后创建本地验收标签；复用现有8000服务，无后台服务重启。当前验收标签已保留为交付页面。
- 先检查1992×956：首次完整有限预算试算由324改善到310天；14.2秒时仍显示“当前最好310天”、已等待、15秒预算及6次改善，结束后改为最终且活动组件消失。运行中收起全部段落，终态仍保持0可见子级；展开后100子级、100施工条、25父级、75逻辑箭线、50等待。
- 在900×956发现到访详情放在轴线上方占用过多纵向空间，已改为与轴并排，并添加前后导航时轴内自动定位；补充键盘语义及选择目标失效清理。修正后进行了第二次15秒内的页面求解，以验证最终构建；最终同为310天。没有为获得指定工期延长预算或重开不限时搜索。
- 第二次原计划等待精确6秒文本的浏览器选择器超时，但随后DOM读数确认10.4秒时仍持续优化、当前最好311天，最后310天；这是采样时点未命中，不是求解失败。无改善连续5秒由上述可控时钟测试证明，未伪称真实求解在该区间完全无改善。
- 键盘操作已验证：全收起/展开、工序选择、逻辑箭线开关（75→0→75）、上一步/下一步、不可定位到访。选中01段水稳底基层详情准确显示FS+0、FS+7，以及2026-11-07至11-13的7天等待。
- 机组轴将本次100任务归成75次到访、8个桩号/幅别轴，保留3次跨桩号系列到访；第4→5次从左幅转右幅，轴内scrollTop到1219.2；17段K678+011—DK0+558单独标为跨桩号系列，可查看第35次到访及前后转场。详见browser-interactions.json。
- 宽窄视口页面本身无横向溢出，图表使用内部滚动。浏览器临时视口已reset，最终恢复1280×720；保存配置按钮仍为“保存配置”，计划日期仍为2026-09-23。桥梁入口只读加载正常。
- 截图：running-wide.png（寻找首解）、running-best-wide.png（运行中，截图滚动位置位于表图）、plan-wide.png（宽屏，截图工具横向拼接存在重复区域，DOM表头实际为4列）、final-build-summary.png（最终摘要）、route-narrow-final.png（窄屏）、route-final.png（恢复默认视口后的最终机组轴）。最终截图以route-final.png为准。

### 非核心问题与未覆盖范围

- 仓库/生命周期验证器实施后重跑，仍仅报告规划时已知的requirements依赖审批和9处历史引用缺失；无070新增违规，未扩展修复。
- 减少动画的CSS媒体规则已在浏览器加载样式中核对；未修改操作系统偏好来进行真实切换。输入变更/旧事件和失败态由定向测试覆盖，本轮没有故意破坏本地服务或保存用户配置来制造异常。
- 当前客户只有一个已分配机组，多机组的数据分组/转场隔离及未分配任务由测试覆盖，多机组选项切换未做真实页面验证；大于100任务的性能不在本轮验收范围。
- 里程轴不是地理道路拓扑；跨桩号系列无权威坐标映射时继续明确降级，不能据此推算距离。


