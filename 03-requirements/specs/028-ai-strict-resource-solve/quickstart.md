# 快速验证：AI 方案严格固定资源单次求解

## 前置条件

- 在仓库根目录执行命令。
- Python 环境已安装 `requirements.txt` 中依赖。
- 前端依赖已安装。
- 不要求配置外部 LLM；本功能验证从已生成资源方案进入排程后的行为。

## 1. 后端针对性测试

```powershell
python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q
```

重点期望：

- AI 单方案只调用一次完整目标求解入口。
- 不调用 `solve_scenario()` 的自动增配路径、最大资源生成或最少资源求解。
- 响应资源快照等于 LLM/用户输入，零工作量资源为 0。
- `plan_status` 与状态矩阵一致。
- 只有 `met` 进入推荐。

## 2. 底层求解与通用入口回归

```powershell
python -m pytest backend/tests/test_scheduler.py -q
```

至少验证：

- 新的一次完整目标入口不先调用基础最短工期求解。
- 三个目标项和硬约束贡献与相同固定输入的现有完整目标模型一致。
- 基线诊断在 AI 路径为 `not_evaluated`，不伪造第二次结果。
- 通用 `solve_scenario()` 在目标延期时仍能执行既有资源增量建议。

## 3. 可复现状态样例

| 样例 | 求解结果 | 目标情况 | 期望 plan_status | 排程 |
|---|---|---|---|---|
| 目标可满足固定资源 | `OPTIMAL` 或 `FEASIBLE` | 无延期 | `met` | 保留 |
| 已证明最优仍延期 | `OPTIMAL` | 延期 | `not_met` | 保留 |
| 限时可行但延期 | `FEASIBLE` | 延期 | `unconfirmed` | 保留 |
| 限时无可用排程 | `UNKNOWN` | 未知 | `unconfirmed` | 空 |
| 有效任务缺少资源类型 | 资源覆盖失败 | 不适用 | `infeasible` | 空 |
| 无强制目标 | `OPTIMAL` 或 `FEASIBLE` | 无目标依据 | `unconfirmed` | 保留 |

每个样例还应断言：

```text
solver_call_count == 1
resource_expansion_attempted == false
alternative_results == []
```

## 4. 前端构建

```powershell
npm.cmd --workspace frontend run build
```

期望 TypeScript 类型检查与 Vite 生产构建通过。

## 5. 页面验证

1. 打开 AI 多方案比选页面并生成经济、平衡、抢工三方案。
2. 记录某方案各资源数量，求解后核对输入快照和详情中的资源数量一致。
3. 将某资源改为 0 并重新求解，确认旧结果失效且系统不自动补资源。
4. 分别查看 `met`、`not_met`、`unconfirmed` 或 `infeasible` 样例的中文状态、延期摘要和诊断。
5. 确认延期方案仍可查看甘特图，但不会进入推荐。
6. 确认三方案均无 `met` 时，推荐区显示“暂无满足目标的推荐方案”。
7. 返回模拟求解页面，验证原有资源增量候选仍可生成。

## 6. 性能验证

在同一输入上记录单方案请求：

- 任务图生成次数：1。
- CP-SAT 调用次数：1。
- 资源增量相关调用次数：0。
- 端到端耗时：不超过 `time_limit_seconds + 2` 秒。

如耗时超过上限，应先检查是否仍有基础排程调用、递归模型重复求解、资源建议调用或请求内时间预算重置。
