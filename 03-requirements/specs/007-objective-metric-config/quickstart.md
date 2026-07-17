# Quickstart：精排目标指标前端展示与配置

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

本文件用于按当前实现验证目标指标展示与配置，不在用户确认前执行代码改动。

## 1. 后端验证

1. 使用旧场景配置求解，确认缺失当前 4 个目标项时后端自动补齐默认值。
2. 使用包含废弃项的历史配置求解，例如：
   - `control_buffer_risk`
   - `risk_related_control_wait`
   - `resource_workload_balance`
   - `unconfigured_normal_balance`
   - `normal_balance`
3. 检查结果：
   - `objective_terms_used` 和 `objective_weights` 仅包含当前 4 个目标项。
   - `objective_breakdown.objective_contributions` 如存在，也仅包含当前 4 个目标项的贡献。
   - `weighted_objective` 等于当前贡献行加权贡献求和。
   - `stats.continuity_metrics`、`stats.normal_balance_metrics` 等仍可作为只读诊断字段存在。

建议命令：

```powershell
pytest backend/tests
```

如测试集较重，优先运行目标配置相关测试，再补全回归测试。

## 2. 前端验证

1. 启动前端页面。
2. 加载任一精排场景。
3. 在目标函数配置区域确认只展示当前 4 个目标项。
4. 修改当前目标项权重并求解。
5. 在结果页确认贡献表展示原始罚分、有效权重和加权贡献。
6. 修改任一目标项后，确认旧生成结果、求解结果和方案对比被清空或标记过期。

建议命令：

```powershell
npm.cmd --prefix frontend run build
```

## 3. 兼容验证

- 打开包含历史 7 项或其他废弃目标项的旧配置，页面不报错。
- 打开没有 `objective_contributions` 的旧结果，页面回退到旧字段汇总，但不从废弃字段合成当前目标贡献。
- 发送未知且非兼容废弃目标项时，后端返回明确校验错误。
- 将所有当前目标项禁用，前端或后端阻止提交。

## 4. 业务验收样例

验收样例应至少覆盖：

- 严格精排成功：当前 4 项目标按启用状态展示贡献。
- 最佳努力或候选复排：目标放松诊断显示为诊断，不出现在目标配置表权重输入中。
- 存在未配置资源普通工程：`normal_balance_metrics` 可显示诊断；`unconfigured_normal_balance` 不显示为当前目标罚分、权重或贡献。
- 槽位均衡、连续性跳跃、换向、同幅间隔等指标只读展示，不出现在配置表权重输入中。
