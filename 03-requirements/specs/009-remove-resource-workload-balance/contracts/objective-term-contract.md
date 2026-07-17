# 契约：目标项移除与兼容

## 请求契约

### 默认有效目标项

`ScheduleStrategyConfig.objective_terms` 的有效目标项不得包含：

```json
"resource_workload_balance"
```

### 历史请求兼容

旧请求允许继续传入：

```json
{
  "schedule_strategy": {
    "objective_terms": {
      "resource_workload_balance": {
        "enabled": true,
        "weight": 100
      },
      "resource_idle": {
        "enabled": true,
        "weight": 1000
      }
    }
  }
}
```

后端必须过滤 `resource_workload_balance`，仅保留其他有效目标项。过滤后如果没有任何有效启用目标项，则返回现有配置校验错误。

## 响应契约

### 目标项集合

以下位置不得包含 `resource_workload_balance`：

- `objective_breakdown.objective_weights`
- `objective_breakdown.objective_terms_used`
- `objective_breakdown.objective_modeling_gates`
- `objective_breakdown.objective_contributions[*].term_id`

### 资源诊断

响应可以继续包含资源工作量原始诊断：

```json
{
  "stats": {
    "resource_organization_analysis": {
      "workload_balance_enabled": false,
      "resource_types": [
        {
          "resource_type": "rotary_drill",
          "min_workload_days": 10,
          "max_workload_days": 18,
          "workload_range_days": 8
        }
      ]
    }
  }
}
```

该诊断不得被解释为目标函数贡献。

## 前端契约

- 目标函数配置表不得展示“同类资源工作量均衡”。
- 目标贡献列表不得展示 `resource_workload_balance`。
- 旧结果 fallback 逻辑不得从 `resource_workload_balance_penalty` 生成当前贡献项。
- 资源诊断区域可展示工作量统计，但需避免显示为“目标已启用”。
