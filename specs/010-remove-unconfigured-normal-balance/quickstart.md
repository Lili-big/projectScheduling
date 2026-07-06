# 快速验证：移除未配置资源普通工程均衡目标

## 前置条件

- 已完成 010 任务实现。
- 本地依赖已安装。
- 不需要修改 `.specify/feature.json`。

## 验证 1：后端目标项集合

运行：

```powershell
python -m pytest backend/tests/test_scheduler.py -q
```

期望：

- 默认 `ScheduleStrategyConfig.objective_terms` 不包含 `unconfigured_normal_balance`。
- `OBJECTIVE_METRIC_DEFINITIONS` 不包含 `unconfigured_normal_balance`。
- 旧请求带 `unconfigured_normal_balance` 时可被过滤。
- 只启用 `unconfigured_normal_balance` 时无法通过“至少一个目标项启用”校验。

## 验证 2：求解结果贡献

使用包含未配置命名资源普通工程的场景求解。

期望：

- `objective_breakdown.objective_contributions[*].term_id` 不包含 `unconfigured_normal_balance`。
- `objective_breakdown.objective_weights` 不包含 `unconfigured_normal_balance`。
- `objective_breakdown.weighted_objective` 不包含未配置资源普通工程均衡贡献。
- `stats.normal_balance_metrics` 仍可看到普通工程分布诊断。

## 验证 3：前端展示

运行：

```powershell
npm.cmd --prefix frontend run build
```

期望：

- 目标函数配置表不显示“未配置资源普通工程均衡”。
- 目标贡献列表不显示该项。
- 普通工程诊断仍能展示普通工程分布信息。

## 验证 4：Excel 导入案例

导入用户当前 Excel 案例并执行“固定资源条件下，推算最短工期”。

期望：

- 求解请求不因旧目标项失败。
- 返回结果不含 `unconfigured_normal_balance` 目标贡献。
- `normal_balance_metrics` 仍可作为诊断字段存在。

## 本次验证记录

- `python -m pytest backend/tests/test_scheduler.py -q`：通过，`126 passed`。
- `npm.cmd --prefix frontend run build`：通过。
- 前端构建产物搜索 `unconfigured_normal_balance` 和“未配置资源普通工程均衡”：无匹配。
- 本地 Excel 样例 `渠溪河特大桥结构设计表.xlsx` 通过 `import_local_bridge_params(default_scenario())` 导入后，完整固定资源场景入口返回 `INFEASIBLE`，未进入可行命名资源精排结果；该结果中不含 `unconfigured_normal_balance` 目标贡献或目标权重。由于该路径没有可行精排结果，`normal_balance_metrics` 未生成；可行结果下的诊断保留由后端回归测试覆盖。
