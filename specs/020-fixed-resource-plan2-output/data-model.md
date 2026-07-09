# 数据模型：固定资源方案2输出提示

## 方案输出状态

描述一次固定资源求解中方案2是否应展示。

字段：
- `alternative_output_status`：枚举，建议值为 `not_applicable`、`output`、`not_output`。
- `alternative_output_reason`：字符串，记录状态原因，建议复用资源建议状态或更细原因。
- `alternative_output_message`：面向用户的短提示。

状态规则：
- `not_applicable`：当前资源已满足目标、当前资源未确认或当前资源物理不可行，不需要进入方案2展示判断。
- `output`：新增资源分支已产生可展示候选，且 `alternative_results` 至少包含一个候选。
- `not_output`：当前资源可查看但目标未满足，新增资源分支已尝试但没有可展示候选。

校验规则：
- `alternative_output_status=output` 时，`alternative_results` 必须包含可展示候选。
- `alternative_output_status=not_output` 时，`alternative_results` 必须为空，且 `alternative_output_message` 必须包含“方案2未输出”或等价用户提示。
- `alternative_output_status=not_applicable` 时，不应展示方案2未输出提示。

## 方案1当前资源结果

沿用 `ScenarioSolveResult.result` 表示。

关键属性：
- 当前资源求解状态。
- `target_achievement` 中的业务目标达成状态。
- `schedule_source` 表示当前资源结果来源。
- 任务、资源分配、里程碑结果和诊断。
- 方案输出状态元数据。

状态规则：
- 当前资源可查看但目标未满足时，方案1必须保留任务和里程碑迟延。
- 新增资源分支失败不得覆盖方案1的当前资源状态。

## 方案2新增资源候选

沿用 `ScenarioAlternativeResult` 表示。

关键属性：
- `role`：候选角色，推荐保持 `minimum_resources`。
- `result`：候选排程结果。
- `generated`：候选资源数量对应的求解输入。
- `metrics`：候选方案摘要。

状态规则：
- 方案2只在候选满足目标并可展示时输出。
- 候选资源数量必须能与方案1形成对比。

## 资源增量建议状态

描述为什么方案2输出或未输出。

典型原因：
- `recommended_resources_verified`：已找到可展示方案2。
- `critical_path_infeasible`：关键路径不可压缩，方案2未输出。
- `resource_upper_bound_infeasible`：资源上限不足，方案2未输出。
- `resource_recommendation_unresolved`：限时内未确认候选，方案2未输出。
- `candidate_resources_full_objective_failed`：候选完整复排未满足目标，方案2未输出。
- `max_resource_generation_error`：最大资源场景生成失败，方案2未输出。

关系：
- 资源增量建议状态解释 `alternative_output_reason`。
- 页面应优先使用 `alternative_output_status` 判断是否展示方案2提示，再使用资源建议状态解释原因。
