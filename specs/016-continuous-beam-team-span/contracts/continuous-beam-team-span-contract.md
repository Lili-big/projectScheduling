# 契约：现浇连续梁联级班组占用

## 输入契约

### ScenarioInput / ScheduleInput

本功能复用现有场景输入和求解输入，不要求用户新增独立配置项。

必须满足：
- 连续梁任务可从结构参数生成，且具备 `bridge_id`、`work_section_id`、`properties.group_index`。
- 连续梁资源池使用 `type = cast_in_place_continuous_beam_team`。
- 资源池 `quantity` 表示当前可投入连续梁班组数。
- 资源池 `max_quantity` 表示资源建议或成本优化可尝试的上限。

### 兼容输入

- 旧场景未显式配置连续梁联级字段时，系统按 `bridge_id + work_section_id + group_index` 派生。
- 若连续梁任务无法派生联，系统应输出诊断，不得静默合并。

## 约束契约

系统必须同时满足以下约束：

1. 联级资源约束：同一连续梁班组同一时间最多占用一个连续梁联。
2. 联内释放规则：同一联内任务不因连续梁班组资源而任务级互斥。
3. 既有连续梁工艺约束：左右悬臂同步、合龙间隔、下部结构完成等继续有效。
4. 非连续梁资源约束：其他命名资源互斥和桩基墩组规则继续有效。

## 输出契约

### ScheduleResult.stats.continuous_beam_team_spans

建议输出为对象，包含以下信息：

| 字段 | 含义 |
|------|------|
| `enabled` | 本次是否应用联级班组规则 |
| `span_count` | 识别出的连续梁联数量 |
| `resource_type` | 固定为 `cast_in_place_continuous_beam_team` |
| `resource_quantity` | 本次可用连续梁班组数量 |
| `spans` | 联级占用明细 |
| `diagnostics` | 联识别或资源配置诊断 |

### spans 明细

| 字段 | 含义 |
|------|------|
| `span_group_id` | 连续梁联 ID |
| `display_name` | 联显示名称 |
| `bridge_id` | 桥梁 ID |
| `work_section_id` | 工区/幅别 ID |
| `group_index` | 连续梁组号 |
| `resource_id` | 连续梁班组 ID |
| `resource_name` | 连续梁班组名称 |
| `start_offset` / `end_offset` | 联级占用偏移 |
| `start_date` / `finish_date` | 联级占用日期 |
| `task_ids` | 联内任务 ID 列表 |

### ScheduledTask 兼容要求

- 连续梁任务可通过 `properties.continuous_span_group_id` 或等价字段追溯所属联。
- 若任务没有任务级 `assigned_resource_id`，前端不得将其解释为资源缺失；应优先查看联级归属。
- 旧结果没有 `continuous_beam_team_spans` 时，前端保持现有展示。

## 错误与诊断契约

系统应覆盖以下诊断：

- 连续梁任务无法识别联。
- 连续梁班组资源池未启用或数量为 0。
- 连续梁联存在，但没有可用班组。
- 最少资源上限仍不足以满足目标时，应说明瓶颈来自连续梁班组联级并发上限或其他约束。

## 验收样例

### 样例 1：1 个班组

输入：
- 左幅连续梁联 A。
- 右幅连续梁联 B。
- `cast_in_place_continuous_beam_team.quantity = 1`。

期望：
- A 与 B 的联级占用窗口不重叠。
- 任一时刻最多 1 个连续梁联占用班组。

### 样例 2：2 个班组

输入：
- 左幅连续梁联 A。
- 右幅连续梁联 B。
- `cast_in_place_continuous_beam_team.quantity = 2`。

期望：
- A 与 B 可重叠。
- A 与 B 分别归属不同连续梁班组。
- 同一联内任务仍按连续梁工艺规则并行或同步。
