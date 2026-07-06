# Quickstart：精排目标指标前端全量展示与配置

本文件用于实现阶段验证，不在用户确认前执行代码改动。

## 1. 后端验证

1. 使用旧场景配置求解，确认缺失新增目标项时后端自动补齐默认值。
2. 使用包含以下新增项的配置求解：
   - `target_relaxation`
   - `resource_slot_balance`
   - `unconfigured_normal_balance`
3. 检查结果：
   - `objective_breakdown.objective_contributions` 存在。
   - 每个可配置目标项都有贡献行。
   - `weighted_objective` 等于贡献行加权贡献求和。
   - `stats.continuity_metrics` 和 `stats.normal_balance_metrics` 仍作为诊断字段存在。

建议命令：

```powershell
pytest backend/tests
```

如测试集较重，优先运行目标配置相关测试，再补全回归测试。

## 2. 前端验证

1. 启动前端页面。
2. 加载任一精排场景。
3. 在目标函数配置区域确认所有可配置目标项展示完整。
4. 修改新增目标项权重并求解。
5. 在结果页确认贡献表展示原始罚分、有效权重和加权贡献。
6. 修改任一目标项后，确认旧生成结果、求解结果和方案对比被清空或标记过期。

建议命令：

```powershell
npm.cmd --prefix frontend run build
```

## 3. 兼容验证

- 打开不包含新增目标项的旧配置，页面不报错。
- 打开没有 `objective_contributions` 的旧结果，页面回退到旧字段汇总。
- 发送未知目标项，后端返回明确校验错误。
- 将所有目标项禁用，前端或后端阻止提交。

## 4. 业务验收样例

验收样例应至少覆盖：

- 严格精排成功：`target_relaxation` 显示不适用或 0 贡献。
- 最佳努力精排：`target_relaxation` 显示迟延/超期罚分及贡献。
- 存在未配置资源普通工程：`unconfigured_normal_balance` 显示罚分、权重和贡献。
- 存在资源槽位均衡罚分：`resource_slot_balance` 独立显示。
- 连续性诊断：跳跃、换向、同幅间隔等指标只读展示，不出现在配置表权重输入中。
