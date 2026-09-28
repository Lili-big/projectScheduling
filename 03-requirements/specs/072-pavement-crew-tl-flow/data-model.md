# 前端局部派生模型

不新增共享协议/存储字段。输入仍为同次ScheduleResult及可选GeneratedScheduleInput。

| 实体 | 来源及字段 |
|---|---|
| VisitLocation扩展 | coordinateGroupKey=工点+桩号前缀；side=left/right/none/unknown；沿用原始桩号、数值起终点及reason |
| CrewFlowGroup | key、label、prefix、min/max；取同次完整输入/结果有效任务，不受当前选中机组影响；组件派生刻度并保留左右两轴 |
| CrewFlowVisit | 复用CrewVisit标识/序号/tasks及location.coordinateGroupKey/side；start/end；xStart/xEnd/xAnchor；unlocatedReason；各工序保留自身时间区间 |
| CrewFlowEdge | key由resourceId/fromKey/toKey组成；from/to为前后全局相邻到访，使用from.end/to.start；kind为same-side/cross-side/external/unlocated/invalid；转场由到访incomingTransfer提供，异常由reason说明 |
| CrewFlowScene | groups/routes，公共timeEnd，来源/局部issues；坐标布局以day及归一化里程输出，组件仅按缩放映射像素 |

任务start/end必须有限、非负且end>start。时间重叠时不推断唯一顺序。转场需匹配同资源/末首任务且全部位于空档；零天与未知不同。日期标签使用plan_start_date+offset，完成日为end−1。

从所有相邻到访产生边，再判定可画性，不能先滤掉不可定位访问后连接。左右同组等里程必同x，距中央基线=offset*k；切机组k和域均保持同快照口径。新快照更新域和时间范围时，选择按稳定ID保留/回退，不修改输入对象。

示例见spec SC-002：4访问/3边，返回A位置不变；第4次开始在day10，不能按ordinal4画在第4天。不分幅/未知幅别保留文字访问而不投到右幅。
