# 实施计划：路面排程结果与机组线路可视化

**工作分支**：codex/road-pavement-engineering | **功能目录**：070-pavement-results-visualization | **日期**：2026-09-27  
**规格**：[spec.md](./spec.md)；状态：用户已确认，实施及核心验证完成，见[tasks.md](./tasks.md)。

## 概要

复用069的同次结果快照和流状态，仅增加前端投影、两级表图与机组里程轴。不添加依赖、HTTP字段、模型或持久化数据。先解决状态及移交语义，再接入任务横道与路线视图。前端派生类型局限于scheduleResults功能内部。

## 技术上下文

- TypeScript 5.7、React 19、Vite 6，既有Node测试、React静态渲染和浏览器验收。
- 平台：本地FastAPI静态前端与现有路面NDJSON流；后端保持原实现。
- 存储：无。折叠、选择、计时均为当前页面/请求内状态。
- 规模：当前25段100任务、多个机组；100任务不新增虚拟列表依赖，受限高度与内部滚动足够。
- 约束：算法、默认15秒预算、资源/工效、主数据、保存配置及桥梁路径不变；无后台心跳或新求解。
- 研究结论见[research.md](./research.md)，数据映射见[data-model.md](./data-model.md)，交互边界见[contracts/results-ui.md](./contracts/results-ui.md)。
- 无阻塞技术未知项。

## 生命周期归属

沿用[规格归属](./spec.md#生命周期归属)。仅在既有scheduleResults功能内新增有明确用途的文件；截图/验证日志在.local-data/logs/。不迁移资产，不改数据库。

## Constitution检查

- 研究前：用户六项反馈、现状代码和真实快照已核对，范围和业务边界明确。
- 设计后：字段来源、日期边界、工艺关系/转场区别、无法定位、历史及失败降级均明确；未增加共享契约/持久化，不将UI推断写成排程规则。
- 规格、设计可验收且主归属唯一，无复杂度豁免。本轮tasks已由用户确认，正式实施门禁满足。

## 设计决策

### D1：使用同一结果快照

Workspace把solved.result和solved.generated一起交给PavementScheduleResults；generated保持可选，以兼容仅有ScheduleResult的历史展示和已有测试。绝不读取当前scenario来补旧结果的桩号、关系、资源或预算。新方案渲染时从同一solved更新，不能在多个事件间拼接。

新增pavementViewModel.ts，只放本功能派生类型与纯映射函数，不扩展全局contracts。结果任务保留全部属性，不修改输入；任务ID对齐缺失时只降级对应图形并显示原因。

### D2：持续求解与精简摘要

- createPavementSolveController保留已有状态/取消/顺序校验，只在PavementLiveState中保留started事件的timeBudgetSeconds（未知为null），沿用elapsed作为最近服务器事件的耗时；不改变流协议。
- Workspace在发起请求时记录单调时钟开始时刻与请求token。PavementSolveProgress每250ms刷新本地“已等待”时间；返回页面从本次开始时刻恢复，终态/中断/输入变更/卸载清理计时器，不创建额外求解请求。
- 使用不定进度动画及明确阶段文字，首解前“正在寻找可行方案”，有方案后“持续优化中，发现更短工期即更新”。动画不代表服务器心跳或已完成百分比。
- 主行显示“初步324天 → 当前最好310天 · 缩短14天”；动态辅行显示“持续优化中 · 已等待8秒 · 计算预算15秒 · 已改善4次”等有来源字段。未知指标省略，不把收到事件数当改善次数。
- 本地已等待包含网络等待，不冒充CP-SAT耗时；服务器实际计算耗时仍放既有折叠详情。达到预算但未收到终态时显示等待结果收尾，继续等待原请求。
- 一行紧凑状态/范围摘要替代原两段；结束后显示“本次优化结束，未证明最优 · 纳入25段/100道工序 · 4段待移交”等。窄屏可自然换行，不重复文案。
- 中断和历史标识优先于成功状态；无方案、初解保留、已证明最优和MODEL_INVALID沿用既有真实诊断。

### D3：移交前提

待移交区标题“移交日期未定 · 请关注最晚需移交日”，说明“已安排在正常段全部完成后；按当前方案，须在所列日期开工前完成移交，实际日期仍待确认”。列名“本方案最晚需移交日”；字段仍使用pending_section_dates.required_handover_date。没有计算全局最迟可移交日，不增设日期求解。无方案不显示旧日期，保留历史blocked_sections。

### D4：两级表格与横道

新增PavementPlanTimeline.tsx，按structure_id（结合工点避免碰撞）分组，组序取generated任务稳定出现顺序，组内按sequence_order和稳定ID，配套仍处第二级。父级汇总起止和任务数，右侧不画作业条；子级表格显示名称、起止、天数和机组。

使用一个共享可滚动容器/行网格：左侧列冻结、右侧时间区内部水平延伸，固定行高保障表格/SVG纵坐标一致；表头和日历刻度粘顶，任务名称截断但可查看完整详情。默认展开，提供全展开/全收起与逐段按钮；宽屏左表右图，窄屏内部滚动且仍可辨识任务名称。复用现有样式令牌和日期语义，不抽取或改写桥梁PlanTimelineView。

横道严格用[start_offset,end_offset)，日期文本用start_date/finish_date（含当天），不靠最小条宽改变日期坐标；很短条使用独立点击热点。日历按真实plan_start_date计算UTC日，不做本地夏令时换算。无效日期/offset保留文本并说明图形无法定位。

### D5：工艺关系与等待

- 关系仅来自generated.schedule_input.precedence_links，并与结果任务ID核对。FS=end→start、SS=start→start、FF=end→end、SF=start→end，端点均按排程边界，不用finish_date的零点代替end_offset。
- SVG折线和箭头用独立样式；默认显示可见工序之间的关系，可整体开关，选中任务突出其入/出边。关系类型、lag_days及可选max_finish_gap_days以详情原值解释；不将软关系升级为强制约束。
- 折叠隐藏端点后不画到父级假箭头，显示有隐藏关系的提示；缺generated时明确无法展示完整关系。不得把predecessor_ids猜成FS+0，也不得把机组顺序画成工艺逻辑。
- wait_intervals与工序使用source_component_id及区间起点等已有事实匹配；同源配套任务需唯一匹配结束边界，零天配套附加等待关联其标识的后续工序并标为开工前等待。不唯一时留在按需未定位详情，不能任意指给第一道任务。
- 等待用浅色虚线/斜纹区间，施工条用实色，提示实际reason和日数；不将相邻任务之间剩余空白算入技术等待，也不把普通非FS/负lag转成养生。
- 移除独立长列表，保留工序点击详情及有需要时的未定位等待详情。等待终点可扩展显示刻度但不能改objective_days或施工完成日。

### D6：机组里程轴

新增PavementCrewRoute.tsx。机组选择框、线路轴、当前到访详情和上一步/下一步替代任务名长串及全部转场列表。

1. 按assigned_resource_id取真实已分配任务，再按start_offset/end_offset/id生成顺序；正常排程同机组任务不重叠，历史重叠/无法排序时明确数据异常，不编造唯一顺序。
2. 连续相同position_id（缺失时使用已知工点/施工段，只作到访归组且幅别未知）的工序合为一次到访；离开后返回新建到访。到访编号是该机组全局实际顺序，不随分轴和里程排序改变。稳定key取resource_id和首任务ID，更新后仍存在则保留选中。
3. 从任务properties.start_chainage/end_chainage严格解析完整桩号为前缀及米，允许常用大小写/空白和小数格式；不从任务名称抽数字，不重写原始字符串。仅两端同前缀且有限数值时可数值定位；同段各任务坐标冲突则该到访不可定位。
4. 轴key为工点ID＋桩号系列＋幅别。幅别只用生成器明确编码在position_id末尾的:left/:right/:none，不从名称猜；缺失归“幅别未知”。轴名称只称桩号系列，不宣称真实道路拓扑。
5. 每轴横向按米比例，区间用起终桩号min/max定位，保留原始端点与顺序标签；不推断段内行进方向。不同到访分行并显示编号，重复位置不遮挡。坐标范围为0时添加显示留白而非伪造工程长度。
6. 仅选中到访及其紧邻前后关系突出：同轴画方向连接；跨轴显示“转至/来自某轴·第N次”，保留一键前后导航；不将非相邻但同轴的点跳连。无选择时显示当前默认首到访。
7. 转场优先用summary.transfers的resource_id/from_task_id/to_task_id匹配相邻末/首任务，显示其半开区间与天数。只有同一已知position_id或本次资源显式transfer_days=0可确认零天；没有记录且不能确认时显示未提供，不将全部作业空档计为转场。
8. 跨桩号系列或缺/非法桩号独立放“无法按统一里程定位”区域，保留施工序号、原文及前后导航。段的construction_length_m只作已有事实详情，不决定坐标/转场距离。

### D7：兼容、交互及验证

无方案不画图，缺机组显示空态；不破坏诊断、输入来源、历史ready日期及计算耗时详情。各控件支持键盘、aria名称和焦点；颜色之外提供文字/线型，减少动态效果媒体查询关闭动画。直播新方案根据稳定ID保持有效选中/折叠，失效时回退首可用项，所有图统一使用最新同次快照。

验证集中在纯投影的不变量、展示状态生命周期、React标记和真实页面。相关测试批次一次运行，再build（内含tsc），不重复整库后端或算法测试。完成后停止扩展测试，只有实际修改/失败才补查。

## 项目结构与精确修改边界

前缀04-demo/frontend/：

- 修改src/app/workflows/solveWorkflow.ts、src/app/Workspace.tsx：保留展示预算和请求计时，传递本次generated与结果。
- 修改src/features/scheduleResults/presenter.ts、ScheduleResultsWorkspace.tsx、styles.css（后两者同属该目录）。
- 新增src/features/scheduleResults/pavementViewModel.ts、PavementSolveProgress.tsx、PavementPlanTimeline.tsx、PavementCrewRoute.tsx。
- 扩展tests/pavementResults.test.mjs、tests/pavementLiveSolve.test.mjs；新增tests/pavementVisualization.test.mjs。既有静态渲染加载器按新增组件导入适配，不引入测试框架。
- 不修改API、全局contracts、后端、架构基线或依赖文件。

文档：本目录全部设计与任务；03-requirements/specs/README.md、agent.md记录“规划待确认”，实施完成后按证据更新；04-demo/README.md只在行为落地后说明操作。

Agent上下文脚本.specify/scripts/powershell/update-agent-context.ps1前序已确认不存在，不创建替代脚本；手动在agent.md记录本轮状态，不把规划写成现状。

## 验证与完成

执行[quickstart.md](./quickstart.md)的定向测试、构建和页面验收。真实同次结果快照用于验证数值投影；不会为本轮引入新的无限试算。已有服务优先复用，后台操作遵守04-demo/runtime/README.md。

创建规格资产后运行仓库/生命周期验证器，记录既有失败和新增问题的区别；不修复无关requirements审批或历史工作包引用。完成任务前记录真实截图、状态及输入未改证据。

## 复杂度跟踪

无违反项。四个局部文件分别负责投影、进度、时间表图和机组轴，均有直接需求来源；不建立通用图表平台，不重构桥梁路径。

