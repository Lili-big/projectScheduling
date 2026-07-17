# 接口契约：精排目标指标前端全量展示与配置

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## 1. 请求契约

### `schedule_strategy.objective_terms`

请求仍使用以 `term_id` 为键的对象结构。

```json
{
  "schedule_strategy": {
    "strategy": "comprehensive",
    "objective_terms": {
      "control_node_late": { "enabled": true, "weight": 10000000000 },
      "makespan_and_soft_milestone": { "enabled": true, "weight": 5000000 },
      "resource_path_continuity": { "enabled": true, "weight": 50000 },
      "resource_idle": { "enabled": true, "weight": 50000 }
    }
  }
}
```

### 兼容要求

- 旧请求缺少新增项时，后端必须补齐默认值。
- 旧请求包含废弃项时，按现有兼容策略忽略。
- 未知项或非法权重返回校验错误。

## 2. 响应契约

### `objective_breakdown.objective_contributions`

后端成功求解时返回统一贡献列表。

```json
{
  "objective_breakdown": {
    "weighted_objective": 123456,
    "objective_contributions": [
      {
        "term_id": "control_node_late",
        "label": "软控制节点迟延",
        "source": "objective",
        "enabled": true,
        "active": true,
        "configured_weight": 1000000000,
        "effective_weight": 1000000000,
        "raw_penalty": 0,
        "weighted_contribution": 0,
        "applies_to": ["control_priority", "comprehensive"],
        "notes": ""
      }
    ],
    "objective_terms_used": {
      "control_node_late": {
        "enabled": true,
        "weight": 1000000000,
        "effective_weight": 1000000000
      }
    },
    "objective_weights": {
      "control_node_late": 1000000000
    }
  }
}
```

### 贡献列表要求

- `weighted_objective` 必须与 `objective_contributions[*].weighted_contribution` 求和对齐。
- 分支不适用但目录存在的目标项可以返回 `active=false` 和 `raw_penalty=0`。
- 继承父项权重的派生项必须在 `notes` 或 `parent_term_id` 中说明来源。
- 旧字段如 `relaxed_target_penalty_days`、`slot_balance_penalty`、`unconfigured_normal_balance_penalty` 可继续保留为兼容或诊断字段，但不得作为当前可配置目标项。

## 3. 目标指标目录契约

实现可采用以下任一方式向前端提供目标指标目录：

- 后端新增只读接口返回目录。
- 后端随场景配置或求解结果返回目录。
- 前端内置目录，但必须与后端测试共同校验，不允许后端新增项后前端静默遗漏。

无论采用哪种方式，目录必须包含：

- `term_id`
- `label`
- `group`
- `description`
- `default_weight`
- `configurable`
- `source`
- `applies_to`
- `legacy_fields`
- 可选 `parent_term_id`

## 4. 前端展示契约

- 配置区展示 `configurable=true` 的目标项。
- 结果页展示 `objective_contributions` 中所有项。
- 诊断区展示只读诊断项，并明确不可配置。
- 没有新贡献列表的旧结果，前端回退到旧 `objective_breakdown` 字段，且标记为旧字段汇总。
- 配置变化后，前端必须清空或标记过期已生成结果、已求解结果和方案对比。

## 5. 错误契约

目标配置错误应返回可定位信息，至少区分：

- `unknown objective_terms`
- `objective_terms.<term_id> must be an object`
- `enabled objective term weights must be between ...`
- `at least one objective term must be enabled`
