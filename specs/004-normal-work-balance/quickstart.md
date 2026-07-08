# 快速验证：普通工程差异化均衡诊断（历史目标口径修正）

## 前置条件

- 已安装后端依赖和前端依赖。
- 当前工作区保留用户已有改动，不执行 git reset 或 checkout。

## 验证 1：已配置资源普通工程不进入未配置资源均衡诊断

1. 构造普通工程任务 A、B、C，均兼容同一启用受限资源，例如旋挖钻。
2. 运行精排。
3. 期望结果：
   - `configured_resource_normal_task_count = 3`
   - `unconfigured_resource_normal_task_count = 0`
   - 不输出当前有效的 `unconfigured_normal_balance_penalty` 目标罚分，或该兼容字段保持 0
   - 资源空闲和资源路径连续性仍可对这些任务产生目标贡献。

## 验证 2：未配置资源普通工程集中风险仅作诊断

1. 构造 6 个普通工程任务，每个工期 2 天。
2. 不提供启用的受限兼容资源候选，使其按资源默认充足处理。
3. 使用按周统计桶运行精排。
4. 期望结果：
   - `unconfigured_resource_normal_task_count = 6`
   - `bucket_loads` 展示多个统计桶的工作量分布
   - 集中程度只作为诊断解释，不作为当前目标罚分或目标贡献
   - 不违反工艺依赖、硬里程碑和控制节点迟延等当前规则。

## 验证 3：控制链任务不被普通工程均衡牺牲

1. 构造一个普通工程任务作为控制对象前置影响任务。
2. 同时构造若干未配置资源普通工程任务。
3. 运行精排。
4. 期望结果：
   - 控制链前置任务不计入未配置资源普通工程诊断统计。
   - 普通工程均衡诊断不会造成控制节点迟延扩大。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
npm.cmd --prefix frontend run build
```

如果 PowerShell 执行策略影响 `npm`，使用项目 README 中的完整 `npm.cmd` 路径。
