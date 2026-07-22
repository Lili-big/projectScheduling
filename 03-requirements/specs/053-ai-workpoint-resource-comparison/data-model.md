# 数据与状态模型：AI 多方案按工点推进资源

## 1. 资源推进工点

表示本轮 AI 唯一允许调整本地资源数量的桥梁工点。

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_id` | string | 稳定 ID；必须存在于当前 `ScenarioInput.project.bridges` |
| `workpoint_name` | string | 后端从当前场景解析的显示名称，不作为身份键 |
| `project_data_version_id` | string/null | 沿用场景当前项目版本；参与场景指纹，不单独创建持久化实体 |

验证规则：

- 页面不自动选择；初始化请求必须显式提供 `workpoint_id`。
- 同名工点以 ID 区分，不允许按名称反查或猜测身份。
- 项目版本或场景变化后，旧选择失效。

## 2. 可调工点本地资源

由现有 `ResourcePool` 投影而来，不新增第二套资源模型。

合法可调条件：

1. `scope_mode == WORKPOINT_EXCLUSIVE`；
2. 资源池或其现有工点 override 稳定归属于目标工点；
3. `enabled == true` 且 `resource_mode == LIMITED`；
4. 当前数量为非负整数，建议数量不超过对应 `max_quantity`；
5. 资源池 ID 与工点 ID 均存在于当前完整场景。

共享池、其他工点本地池、停用池、无限资源和未知池均不是可调实体。

## 3. 单工点资源方案

沿用 `ResourceAssistantPlan` 并增加目标身份。

| 字段 | 类型 | 新旧规则 |
|---|---|---|
| `target_workpoint_id` | string/null | 新生成方案必填；历史方案允许缺失以兼容读取 |
| `target_workpoint_name` | string/null | 新生成方案由后端解析；仅展示，不用于校验 |
| `resource_pools` | ResourcePool[] | 始终为完整项目资源快照；只有目标工点合法本地数量可不同于当前场景 |
| `profile` | economy/balanced/crash/custom | 三个生成档位保持现有语义 |
| `solve_status` | 现有状态枚举 | 工点切换或资源变化后进入失效/清空流程 |

不变量：

- 同一轮三方案的 `target_workpoint_id` 必须一致。
- 非目标工点池与共享池必须和请求场景逐池一致。
- 不新增、删除、重命名或按类型合并资源池。
- 经济、平衡、抢工的目标工点资源数量保持合法相对梯度。

## 4. 初始化请求与生成记录

`ResourceAssistantInitialRequest` 增加：

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_workpoint_id` | string | 必填、非空、属于当前场景 |

`ResourceAssistantGenerationRecord.input_fingerprint` 同时覆盖完整场景和目标工点 ID。LLM 上下文增加目标工点摘要与 `editable_resource_pools`，但继续保留完整项目画像和当前资源池供解释全项目影响。

## 5. 全项目方案结果

`ResourceAssistantPlanResult` 继续使用现有结构。其 `generated`、`result`、`metrics` 和诊断覆盖完整项目；`input_fingerprint` 包含完整场景、完整方案资源池和目标工点 ID。

方案结果不新增“单工点工期”或“单工点任务数”等平行指标。页面通过关联 `ResourceAssistantPlan.target_workpoint_*` 说明资源变量范围。

## 6. 状态转换

```text
未选择工点
  -> 选择工点
已选择、无方案
  -> 生成三方案
三方案待求解
  -> 独立求解 -> 部分/全部有结果 -> 比较/推荐/详情/基准确认

任一当前状态
  -> 切换工点或项目版本变化
未选择或新工点已选择、旧方案/结果/推荐/详情/基准状态清空
```

迟到响应只有在其请求令牌同时匹配当前场景指纹和目标工点 ID 时才可落地。

## 7. 兼容策略

- 历史 `ResourceAssistantPlan` 缺少目标字段时仍可反序列化和只读展示。
- 历史计划快照不迁移、不删除、不推断目标工点。
- 新的初始化、更新、求解和基准确认链路拒绝缺失目标身份的方案，并返回可行动错误。
- 前端类型与后端 Pydantic 模型同步允许历史空值，但新生成响应必须实际返回非空值。
