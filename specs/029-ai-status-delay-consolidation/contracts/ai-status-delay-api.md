# 接口契约：AI 方案三态与最大延期

## 1. 影响范围

保持现有接口路径和请求体不变：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/solve-plans`
- `POST /api/ai-resource-assistant/compare-results`
- `POST /api/ai-resource-assistant/generate-recommendation`

只向响应中的方案结果和目标评估增加可空字段。

## 2. 新增响应字段

```json
{
  "plan_result": {
    "schedule_outcome_status": "duration_target_not_met",
    "schedule_outcome_reason": "late_unconfirmed",
    "plan_status": "unconfirmed",
    "solver_status": "FEASIBLE",
    "result": {
      "stats": {
        "target_achievement": {
          "schedule_outcome_status": "duration_target_not_met",
          "schedule_outcome_reason": "late_unconfirmed",
          "max_target_delay_days": 12,
          "target_status": "unconfirmed",
          "hard_milestone_late_days": 17,
          "fixed_duration_overrun_days": 8,
          "target_present": true,
          "has_schedule": true,
          "optimality_proven": false
        }
      }
    }
  }
}
```

新字段均为向后兼容字段；旧客户端可忽略，新客户端必须优先使用。

## 3. 状态原因与页面说明

| 主状态 | 原因 | 页面说明 |
|---|---|---|
| `duration_target_met` | `target_met` | 当前资源已满足强制工期目标，可参与推荐。 |
| `duration_target_not_met` | `proven_late` | 当前固定资源下最优排程最大延期 X 天。 |
| `duration_target_not_met` | `late_unconfirmed` | 当前排程最大延期 X 天，尚未证明不存在更优排程。 |
| `no_feasible_schedule` | `time_limit_no_schedule` | 限时内未获得可行排程，不据此判断资源一定不足。 |
| `no_feasible_schedule` | `proven_infeasible` | 已证明当前资源无法形成可行排程。 |
| `no_feasible_schedule` | `resource_coverage_missing` | 当前有效任务缺少兼容资源，显示具体诊断。 |
| 空 | `target_missing` | 缺少工期目标，无法评估。 |

## 4. 推荐契约

推荐候选资格：

```text
schedule_outcome_status == duration_target_met
或（历史结果缺少新字段且 plan_status == met）
```

其他状态不得补位。无候选时继续返回空推荐和解释原因。

## 5. 历史兼容契约

- 旧响应和历史计划快照可以缺少全部新字段。
- 服务器模型必须以默认空值解析旧数据。
- 页面按 `data-model.md` 的回退矩阵映射，不向存储写回。
- `plan_status`、`target_status` 和旧中文诊断暂不删除。
- 计划版本 ID、版本号、指纹和快照内容不因读取发生变化。

## 6. 失效与异常

- 资源数量、项目场景或方案发生变化时，旧结果整体删除，因此新三态和最大延期同步失效。
- 技术异常、模型无效或请求失败时，新三态为空，页面显示原工作流失败状态。
- 新字段缺失不得导致方案卡、对比、推荐或计划执行页面崩溃。
