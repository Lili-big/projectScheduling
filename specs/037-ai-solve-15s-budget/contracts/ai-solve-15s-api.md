# 接口契约：AI 单方案 15 秒求解预算

## 1. 接口范围

保持现有请求结构和接口路径：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`

不新增用户可编辑时限、阶段开关、目标权重或重试参数。

## 2. 新结果预算口径

默认 AI 单方案响应必须满足：

```json
{
  "optimization_stages": {
    "primary": {
      "attempted": true,
      "configured_budget_seconds": 15.0
    },
    "secondary": {
      "attempted": false,
      "configured_budget_seconds": 0.0,
      "skipped_reason": "not_applicable"
    },
    "selected_stage": "primary",
    "total_budget_seconds": 15.0
  }
}
```

同时满足：

- `result.stats.solver_call_count=1`；
- `result.stats.performance_path=ai_strict_fixed_resource_single_stage`；
- `result.stats.configured_time_limit_seconds=15.0`；
- `result.stats.target_achievement.time_budget_seconds=15.0`；
- `resource_expansion_attempted=false`。

## 3. 批量边界

- `solve-plan` 每次请求为当前方案配置 15 秒。
- `batch-solve` 中每套方案分别配置 15 秒。
- 三套方案不是共享总计 15 秒。

## 4. 错误与兼容

- 15 秒内未获得排程时，沿用现有响应状态和诊断，不触发重试或资源扩充。
- 历史响应中的预算值原样解析，不转换为 15 秒。
- 请求字段、响应字段、状态码和历史原因枚举均不改变。
- LLM 调用超时、通用模拟求解及其他非 AI 入口不属于本契约。

## 5. 页面契约

- 当前 AI 多方案比选页面显示“单方案固定资源求解最长 15 秒”。
- 新结果的阶段预算与实际服务端配置一致。
- 历史结果继续显示其原始阶段事实。
