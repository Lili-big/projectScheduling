# 数据与状态模型：导航目录与 AI 多方案比选重构

## 导航组 `NavigationGroup`

表示左侧一级业务目录，仅存在于前端页面元数据中。

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `id` | 分组稳定标识 | `projectParameters` 或 `prePlanning` |
| `label` | 用户可见编号和名称 | 分别为“1. 项目基本参数”“2. 前期策划” |
| `items` | 有序页面入口 | 不得包含 `resultsMvp` |
| `expanded` | 当前会话展开状态 | 首次均为 `true`；整体侧栏折叠不改变 |

## 导航项 `NavigationItem`

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `key` | 现有 `TabKey` | 保留 `resourceAssistant`、`results`；删除 `resultsMvp` |
| `label` | 编号后的用户可见名称 | 必须与工作区标签一致 |
| `icon` | 折叠侧栏中的识别图标 | 复用现有图标 |

## AI 页面视图状态 `ResourceAssistantViewState`

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `mode` | 当前页面模式 | `comparison` 或 `detail` |
| `detailPlanId` | 当前详情方案 | `detail` 时必须指向仍有 `plan_result` 的方案 |

### 状态转换

```text
comparison --查看方案详情--> detail
detail --返回多方案比选--> comparison
detail --方案结果失效--> comparison
comparison/detail --项目场景变化--> comparison（并清空方案会话）
```

## 只读结果上下文 `ReadOnlyPlanDetailContext`

由现有前端对象组合，不新增后端字段。

| 来源 | 使用内容 | 规则 |
| --- | --- | --- |
| 当前 `ScenarioInput` | 项目结构、工艺、逻辑、里程碑和策略 | 作为基础场景 |
| `ResourceAssistantPlan` | `scenario_id`、`scenario_name`、`profile`、`resource_pools`、`solve_status` | 资源池必须覆盖基础场景资源池 |
| `ResourceAssistantPlanResult` | `generated`、`result`、`diagnostics`、`metrics` | 必须与当前方案标识一致 |

### 校验规则

- `plan.scenario_id` 必须等于 `planResult.scenario_id`。
- 详情入口只在 `planResult` 存在时展示。
- 如果 `generated` 或 `result` 缺失，详情展示诊断空态，不使用其他结果补齐。
- 修改资源数量后，删除对应 `planResult`，并使详情状态退出。
