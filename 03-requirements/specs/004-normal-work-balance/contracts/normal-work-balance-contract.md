# 契约：普通工程差异化均衡诊断（历史目标口径修正）

## 输入契约

本变更不新增用户输入字段。系统继续使用现有排程输入：

| 输入 | 用途 |
| --- | --- |
| 任务管控级别 | 判断普通工程、控制工程、关键工程 |
| 任务兼容资源类型 | 判断是否可能需要受限资源 |
| 启用资源池/命名资源 | 判断是否存在受限兼容资源候选 |
| 普通工程统计桶配置 | 决定按周或按月诊断未配置资源普通工程分布 |
| 目标函数配置 | 继续控制当前 4 个目标项；不恢复 `normal_balance` 或 `unconfigured_normal_balance` |

## 输出契约

### `objective_breakdown`

当前实现不得新增或恢复以下目标解释字段作为有效目标贡献：

| 字段 | 含义 |
| --- | --- |
| `unconfigured_normal_balance_penalty` | 历史字段；当前不得作为有效目标罚分输出 |
| `unconfigured_normal_balance_weight` | 历史字段；当前不得作为有效目标权重输出 |
| `unconfigured_normal_balance_score` | 历史字段；如保留只能作为诊断评分 |
| `normal_balance_penalty` | 兼容字段；当前应保持 0 或不输出，不得误指全部普通工程 |

### `stats.normal_balance_metrics`

应区分以下信息：

| 字段 | 含义 |
| --- | --- |
| `normal_task_count` | 普通工程任务总数 |
| `configured_resource_normal_task_count` | 已配置受限资源普通工程数量 |
| `unconfigured_resource_normal_task_count` | 未配置受限资源普通工程数量 |
| `bucket_loads` | 未配置受限资源普通工程按桶分布 |
| `balance_score` | 未配置受限资源普通工程诊断评分 |

## 前端展示契约

- 不新增前端可编辑目标项。
- 如展示普通工程分布，应使用“未配置资源普通工程诊断”或等价名称。
- 旧的“普通任务分布评分”文案不得暗示全部普通工程都被时间均衡目标优化。

## 兼容要求

- 旧配置包含 `normal_balance` 时继续忽略，不报错。
- 旧配置包含 `unconfigured_normal_balance` 时继续忽略，不报错。
- 未消费新增字段的前端仍能正常渲染。
- Netlify 演示 API 不要求实现 CP-SAT parity，但不得输出与 Python 主链路冲突的目标解释。
