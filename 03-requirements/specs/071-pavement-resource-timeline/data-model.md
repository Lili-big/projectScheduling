# 数据模型与来源

无共享/持久化字段变化。前端新增局部派生类型：

| 实体 | 字段与来源 |
|---|---|
| ResourceTimelineRow | id/name：assigned_resource_id/name或同次generated资源；tasks/segments；periodStart/periodEnd；workDays/transferDays/idleDays/workRate；longestIdle时间片或null；issues |
| ResourceTimeSegment | key、kind(work/transfer/idle/unknown)、start/end半开偏移；task/from/to引用同次ScheduledTask，可选 |
| buildResourceTimeline返回值 | rows、axisEnd、unassignedCount；轴起点固定为0，无任务及局部异常由组件提示 |

任务区间取result.tasks；转场取pavement_summary.transfers。generated仅补充同次资源清单、名称和显式0天转场。wait_intervals不得当成资源占用。期外背景为轴减去分析期，不计idle。分析期为空或数据异常时指标用null，显示“—”，不使用NaN/Infinity或填0。

有效区间须有限、start>=0且end>start；零天转场可确认但不画占用条。去重并集消除重复计数；不同真实作业重叠必须提示异常，不能靠并集合计掩盖。未知转场阻止确定空闲汇总。最长空闲并列时默认最早者；全部空闲段仍可查看。

厚度规则：unit=m时thickness_m不参与计算校验；留空或已有取值均不影响长度排程。其他单位现状不变，width和净长等原校验保留。geometric+m的数量须等于净长，验证不依赖厚度是否存在。厚度未知的吨位显示—，无假造默认值。
