# 数据模型

## 页面级预算草稿

- 仅 PavementWorkspace 内存状态；字符串初值 15，允许临时为空以便输入。
- 有效值解析为大于 0 的有限秒数；无效时显示错误并禁用两个求解按钮。
- 不写 scenario、业务 fingerprint、localStorage、主数据或保存配置；计算开始冻结快照，计算中禁用编辑。

## PavementIdleOptimizeRequest

既有 scenario、baseline 不变。增加可选 time_budget_seconds：float 或 null，默认 null；非 null 时 gt=0、allow_inf_nan=False。

有效预算 = 独立字段非 null 时的值，否则 scenario.time_limit_seconds。缺省兼容旧调用方。预算字段仅影响执行截止时间、启动事件和本轮耗时元数据，不参与基准身份。

## 既有结果与状态

不增加结果字段。started.time_budget_seconds 与 pavement_idle_optimization.time_budget_seconds 记录有效预算；普通求解沿用 pavement_optimization.time_budget_seconds。第一阶段指标继续记录第一阶段实际预算。

基准 generated.schedule_input、summary.input_fingerprint、baseline_input_fingerprint 继续保持原含义，不将单次预算覆盖回原计划。运行状态、失败/中断和最优证明范围沿用 074。
