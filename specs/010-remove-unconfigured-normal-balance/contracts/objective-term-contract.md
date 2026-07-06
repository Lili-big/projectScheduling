# 契约：未配置资源普通工程均衡目标移除与兼容

## 请求契约

### 默认有效目标项

`ScheduleStrategyConfig.objective_terms` 的有效目标项不得包含：

```json
"unconfigured_normal_balance"
```

### 历史请求兼容

旧请求允许继续传入：

```json
{
  "schedule_strategy": {
    "objective_terms": {
      "unconfigured_normal_balance": {
        "enabled": true,
        "weight": 10
      },
      "resource_idle": {
        "enabled": true,
        "weight": 1000
      }
    }
  }
}
```

后端必须过滤 `unconfigured_normal_balance`，仅保留其他有效目标项。过滤后如果没有任何有效启用目标项，则返回现有配置校验错误。

## 响应契约

### 目标项集合

以下位置不得包含 `unconfigured_normal_balance`：

- `objective_breakdown.objective_weights`
- `objective_breakdown.objective_terms_used`
- `objective_breakdown.objective_modeling_gates`
- `objective_breakdown.objective_contributions[*].term_id`

### 普通工程诊断

响应可以继续包含普通工程分布诊断：

```json
{
  "stats": {
    "normal_balance_metrics": {
      "normal_task_count": 12,
      "configured_resource_normal_task_count": 7,
      "unconfigured_resource_normal_task_count": 5,
      "bucket_loads": [],
      "balance_score": 100,
      "metric_scope": "unconfigured_resource_normal_work"
    }
  }
}
```

该诊断不得被解释为目标函数贡献。

## 前端契约

- 目标函数配置表不得展示“未配置资源普通工程均衡”。
- 目标贡献列表不得展示 `unconfigured_normal_balance`。
- 旧结果 fallback 逻辑不得从 `unconfigured_normal_balance_penalty` 或 `normal_balance_penalty` 生成当前贡献项。
- 普通工程诊断区域可展示 `normal_balance_metrics`，但需避免显示为“目标已启用”。
