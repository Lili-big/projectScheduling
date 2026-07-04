# 契约：普通工程差异化均衡目标

## 输入契约

本变更不新增用户输入字段。系统继续使用现有排程输入：

| 输入 | 用途 |
| --- | --- |
| 任务管控级别 | 判断普通工程、控制工程、关键工程 |
| 任务兼容资源类型 | 判断是否可能需要受限资源 |
| 启用资源池/命名资源 | 判断是否存在受限兼容资源候选 |
| 普通工程统计桶配置 | 决定按周或按月诊断未配置资源普通工程分布 |
| 目标函数配置 | 继续控制现有 7 项目标；不恢复 `normal_balance` |

## 输出契约

### `objective_breakdown`

应新增或更新以下解释字段：

| 字段 | 含义 |
| --- | --- |
| `unconfigured_normal_balance_penalty` | 未配置受限资源普通工程均衡罚分 |
| `unconfigured_normal_balance_weight` | 后端固定低优先级权重 |
| `unconfigured_normal_balance_score` | 面向展示的均衡评分 |
| `normal_balance_penalty` | 兼容字段，可与新罚分保持一致或继续作为旧字段解释，但不得误指全部普通工程 |

### `stats.normal_balance_metrics`

应区分以下信息：

| 字段 | 含义 |
| --- | --- |
| `normal_task_count` | 普通工程任务总数 |
| `configured_resource_normal_task_count` | 已配置受限资源普通工程数量 |
| `unconfigured_resource_normal_task_count` | 未配置受限资源普通工程数量 |
| `bucket_loads` | 未配置受限资源普通工程按桶分布 |
| `balance_score` | 未配置受限资源普通工程均衡评分 |

## 前端展示契约

- 不新增前端可编辑目标项。
- 如展示普通工程分布，应使用“未配置资源普通工程均衡”名称。
- 旧的“普通任务分布评分”文案不得暗示全部普通工程都被时间均衡目标优化。

## 兼容要求

- 旧配置包含 `normal_balance` 时继续忽略，不报错。
- 未消费新增字段的前端仍能正常渲染。
- Netlify 演示 API 不要求实现 CP-SAT parity，但不得输出与 Python 主链路冲突的目标解释。
