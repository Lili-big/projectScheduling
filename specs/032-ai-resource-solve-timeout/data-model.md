# 数据模型：AI 资源方案求解时限调整

## 总体结论

本功能不新增或修改共享数据模型、接口字段、持久化实体和历史数据。仅在 AI 严格固定资源方案进入求解前，对现有场景副本的 `time_limit_seconds` 应用 30 秒专项值。

## 现有实体与本功能约束

### `ScenarioInput`

- **相关字段**：`time_limit_seconds`。
- **现有含义**：当前场景的求解时限，默认值仍为 15 秒。
- **本功能行为**：页面原始场景不修改；AI 资源助手为所选方案创建的求解场景副本使用 30 秒。
- **验证规则**：必须大于 0；非 AI 入口仍接收和使用原始场景值。

### `ResourceAssistantPlan`

- **相关字段**：`scenario_id`、`scenario_name`、`resource_pools`。
- **本功能行为**：内容不变；三类方案均使用同一 30 秒求解预算。
- **关系**：一个方案与一个当前项目场景组合后形成一次严格固定资源求解输入。

### `GeneratedScheduleInput`

- **相关字段**：`schedule_input.time_limit_seconds`。
- **本功能行为**：AI 方案求解响应中应为 `30.0`，用于证明专项预算已传入任务生成后的求解输入。

### `ScheduleResult.stats`

- **相关字段**：`configured_time_limit_seconds`、`wall_time_seconds`、`solver_call_count`、`resource_expansion_attempted`、`target_achievement.time_budget_seconds`。
- **本功能行为**：配置时限和目标评估预算应为 30 秒；实际耗时可以小于 30 秒；调用次数仍为 1；资源增配仍为 `false`。

## 状态转换

本功能不新增状态。30 秒到期后的状态继续沿用现有规则：

```text
提前证明最优且有排程 -> OPTIMAL
限时内获得排程但未证明最优 -> FEASIBLE
限时内未获得排程 -> UNKNOWN
证明物理不可行 -> INFEASIBLE
```

业务三态及原因继续由现有映射生成，不因预算值变化而改变语义。

## 兼容性

- 历史请求和历史基准计划无需迁移。
- 前端类型无需变更。
- Netlify 演示 API 无独立 AI 严格资源求解实现，本功能不新增镜像改动。
- 外部 LLM 与本地回退生成的方案使用同一处理路径。
