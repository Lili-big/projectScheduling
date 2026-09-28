# 前端展示数据模型

只定义scheduleResults内存投影与请求内展示状态，不修改后端、HTTP模型或保存结构。所有日期、桩号、机组和关系来自同一ScenarioSolveResult。

## 数据入口

| 来源 | 使用 | 缺失行为 |
| --- | --- | --- |
| result.tasks | 子级作业、施工段、机组排序、桩号properties及position_id | 无任务不画图；字段缺失保留可读文字 |
| generated.schedule_input.precedence_links | FS/SS/FF/SF、lag、max_finish_gap、severity | 提示逻辑数据缺失；不从predecessor_ids猜类型 |
| generated.schedule_input.tasks | 稳定分组/层序与同次输入对应校验 | 使用结果已有分组及顺序；不读取当前scenario |
| generated.schedule_input.resources | 已知的机组标识、零天转场配置 | 非零真实转场仍可读；不能确认0则未知 |
| result.pavement_summary.wait_intervals/transfers | 实际等待、相邻转场半开区间 | 不能用任务空档补造 |
| result.stats.pavement_handover及summary.pending_section_dates | 范围、待移交及本方案要求日期 | 保留历史blocked；无可行方案日期为空 |
| result.pavement_optimization | 初解/当前最好、改善次数、最优性与真实计算耗时 | 缺失项不伪造为0 |

## 请求内显示状态

- 保留PavementLiveState既有status、solved、error、sequence、elapsed。
- 新增内部timeBudgetSeconds: number或null，由校验后的started事件赋值；不改变PavementSolveEvent。
- Workspace保存本次requestStartedAt（performance.now单调时钟），与请求token绑定，不持久化。
- elapsed仍指最近服务器事件秒数；UI本地waitedSeconds独立计算并标“已等待”，不当作CP-SAT秒数。
- 状态：idle→running（无方案→已有方案）→complete或interrupted。终态清理本地计时器；无改善不改变状态，超过预算不自动完成。
- 新请求重置；旧token回调丢弃；输入改变取消旧请求并保留历史标记。

## 施工段、工序和图形

- SectionGroup：稳定key（工点ID＋structure_id）、name、pending、children、最早开始/最晚完成。没有施工bar。
- TaskRow：task.id、完整任务引用、所属段、显示层序；start/end是原offset，工期显示原duration_days。
- LogicEdge：原link.id、两端task ID、relationship、lag及可选最大完成间隔/severity；端点规则按plan D5，未找到任务不造边。
- WaitBand：原等待引用、匹配的task ID或null、start/end、reason、归属类别。普通等待以同source_component_id且task.end_offset==start唯一匹配；附加等待保留其后续工序引用和真实区间。若歧义则不画到单个工序，只显示未定位详情。
- 时间单位为日历天，区间均[start,end)，日期文本末日为end−1；结束边界用于逻辑关系。零长区间不展示负一天日期。

## 机组到访与里程轴

- CrewRoute：resourceId/name、按真实时间的Task序列、Visit序列。重叠异常显示提示，不假定ID排序就是已证明施工顺序。
- Visit：稳定key为resourceId＋首任务ID；ordinal为当前机组1起全局施工序号；positionId、structureId、tasks、start/end、可定位信息和前后Visit。
- 连续同position合并；A→A→B→A得到三次到访，最后A不能合并到第一次。每个已分配任务只属于一次到访。
- Chainage：原字符串、标准化prefix、米数；完整格式解析失败即不可定位。标准化不改原始主数据。
- MileageAxis：workpointId＋prefix＋side，min/max为该轴有效区间范围；side只用已知position_id后缀或未知。名称使用工点ID/可用标签＋桩号系列＋幅别，不凭空起道路名。
- LocatedVisit：start/end同prefix且有限；区间按min/max投影，保留原始端点方向。同段任务坐标不一致标为冲突。
- UnlocatedVisit：混合prefix、缺少/非法桩号或坐标冲突；保留所有原始桩号、序号、任务和前后导航。不能用construction_length_m代替定位。
- TransferDetail：匹配真实相邻末/首任务的非零转场；已知同位置或快照资源明确0可取0；其余unknown。任务空档不可代替transfer天数。

## 更新与验证不变量

1. 纯映射不修改solved/result/generated；不写存储、不触发求解。
2. 同一方案的表格、关系、等待、路线和条件日期一同替换，不混用事件或当前输入。
3. 折叠按段ID、机组按resourceId、到访按稳定key、任务按task.id保留；消失后回退，不保留过期详情。
4. 无可行方案不展示假计划；旧结果缺逻辑或桩号仅降级对应视图，已有合法数据仍可读。
