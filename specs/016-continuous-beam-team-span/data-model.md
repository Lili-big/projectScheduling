# 数据模型：现浇连续梁联级班组占用

## 连续梁联

**含义**：现浇连续梁班组占用的业务单位，由一组联内连续梁任务组成。

**识别字段**：
- `bridge_id`：桥梁 ID。
- `work_section_id`：工区或幅别 ID。
- `group_index`：连续梁组号，来源于任务 `properties.group_index`。

**派生字段**：
- `span_group_id`：稳定联级 ID，建议由 `bridge_id`、`work_section_id`、`group_index` 拼接形成。
- `task_ids`：该联内所有现浇连续梁任务 ID。
- `display_name`：用于结果解释的联名称，例如“左幅连续梁组 2”。

**校验规则**：
- 只有 `component_type = cast_in_place_continuous_beam` 或 `structure_type = continuous_beam` 的任务参与。
- 缺少 `bridge_id`、`work_section_id` 或 `group_index` 时，不得静默归入默认联；应产生可解释诊断。
- 一个联至少包含 1 个实际生成任务。

## 连续梁班组资源池

**含义**：承担连续梁联级施工组织的资源池。

**关键字段**：
- `type = cast_in_place_continuous_beam_team`。
- `quantity`：当前固定资源下最多可并行施工的连续梁联数。
- `max_quantity`：最少资源或资源建议分支可尝试的最大连续梁联并行数。
- `enabled`：是否启用该资源池。
- `resource_mode`：若为不受限资源，则联级班组互斥不应作为受限资源约束。

**校验规则**：
- `quantity = 1` 表示跨联串行。
- `quantity = 2` 表示最多两联并行。
- `quantity = 0` 或资源池禁用时，应按既有资源不足规则输出诊断。

## 联级占用窗口

**含义**：连续梁联占用某个班组的时间范围。

**字段**：
- `span_group_id`：连续梁联 ID。
- `resource_id`：被选择的连续梁班组 ID。
- `resource_name`：班组名称。
- `start_offset` / `end_offset`：联级占用开始和结束偏移。
- `start_date` / `finish_date`：联级占用开始和结束日期。
- `task_ids`：纳入该窗口的联内任务。

**计算口径**：
- `start_offset` 等于联内实际生成任务的最早开始。
- `end_offset` 等于联内实际生成任务的最晚完成。
- 同一 `resource_id` 下的联级占用窗口不得重叠。

## 联内连续梁任务

**含义**：现有任务视图中的连续梁任务，例如 0 号块、标准段、边跨连续段、边跨合龙段、中跨合龙段。

**保持不变**：
- 任务 ID、名称、工期、工程量、前后置关系、控制等级、里程碑范围。
- 左右悬臂标准段同步和合龙完成间隔等连续梁专用规则。

**新增解释关系**：
- 任务可追溯到 `span_group_id`。
- 任务可通过所属联追溯到联级班组归属。

## 排程结果扩展

**目标**：让用户看懂联级资源组织，同时保持旧结果兼容。

**建议承载位置**：
- `ScheduleResult.stats.continuous_beam_team_spans`：联级占用汇总和诊断。
- `ScheduledTask.properties.continuous_span_group_id`：任务所属联追溯字段。
- `ResourceAllocation` 可新增或复用记录表达联级占用，但不得让用户误解为联内任务级互斥。

**兼容规则**：
- 旧结果缺少联级字段时，前端不报错。
- 非连续梁任务不新增联级字段要求。
