# 任务预览与工序链数据口径

不新增后端共享字段或持久化结构。预览复用ScenarioInput、GeneratedScheduleInput、Task、PrecedenceLink；本轮路面readiness和结果完成语义的变化见下文。

## PreviewState

- status：idle / loading / ready / error。
- fingerprint：当前项目、主数据版本和当前内存场景的指纹，范围固定ALL。
- generation：与该指纹一致的生成结果；旧结果可保留为历史，但不可标为当前。
- error：请求级失败信息；业务validation随generation保留。
- requestSequence：递增请求身份，旧请求、离页后的响应不得提交；同指纹结果复用，显式重试例外。

状态：首次进页idle→loading→ready或error；输入变化立即失效并合并快速修改；请求错误保留骨架和明确失败，不自动循环重试；离页使未完成提交资格失效。

## TaskGroup / TaskRow（展示投影）

分组键为workpoint_id + structure_id，名称来自当前权威主数据；顺序按主数据和层序。

核心行稳定身份为component_id，对齐backend task.id；配套行身份为step.id，仅duration_days>0存在。行保留task_kind、结构层/工序名称、实际process_id/productivity_rule_id、工程量/单位、工效/单位、duration_days、前置列表及诊断。

duration_days未算出时为null/待完善，不伪造0。已计算行的数值全部来自同一份后端生成结果。工效下拉选中值以当前显式覆盖/主数据继承与后端实际方案一致；无效ID保留为失效项待纠正。

## RelationRow（展示投影）

字段：predecessor/successor身份和名称、relationship、lag_days（允许null表示未确认）、source（统一/分段/原养生配套/固定顺序）、status（confirmed/pending/invalid）。

已确认边对齐后端真实边。既有依赖规则可用于识别缺项：缺失间歇显示FS+N（待确认）等；缺失前置任务时显示其主数据名称及待生成，不接受后端临时跨层边。跨段固定关系保留来源段信息；不直接修改原配置或生成结果。

## 显示与保存边界

任务页默认展示全部段，不受模拟页单工点选择隐藏影响。分组折叠只是本地显示状态。工效选择仍写scenario.task_overrides；仅点击保存才调用原配置API，不持久化任务预览。旧求解结果失效沿用现有指纹行为。

## 关系与历史条件

dependency_rules是唯一层间等待编辑入口；分段覆盖>统一规则>旧layer_conditions.wait_days。显式null不回退成确认值。旧条件仍在存储中，预览/载入不会自动迁移；编辑关系只写关系字段。已存非末层accepted_available_date仍生效，在对应分段关系行的可选条件中维护，修改日期保留该旧条件的wait_days/basis_note。

每个position按启用层序确定末层；没有同段后继的末层不再使用其历史wait_days/accepted_available_date，不要求wait_basis。缺失中间层不改变主数据上的末层判定，也不能据此放行不完整求解。单层段即为末层，不产生层间养生输入。

## 本轮生成输入与结果

- 新生成readiness_conditions为空；末层wait_days/accepted_available_offset省略或0，仅代表本轮不计算，不宣称现场无需养生。配置历史不变。
- 新直接求解载荷可无末层wait_basis；存在旧readiness_conditions或非零末层等待/验收边界时，返回明确的重新生成诊断。其他层间、资源、路床及引用校验保留。
- 新结果readiness为空；objective_breakdown.objective为earliest_construction_finish；objective_days=max(task.end_offset)，plan_finish_date=construction_finish_date=start_date+max(end_offset)-1。
- ready_offset/date沿用原技术边界定义，兼容字段不用于本轮业务完成展示；不再展示“养生后交付可用”。末层完成里程碑以实际finish_date为准，不因边界表示多一天。
- 旧目标/含readiness的结果保留为历史并标记需重新求解；不自动删除或用新文案重新解释旧数据。
