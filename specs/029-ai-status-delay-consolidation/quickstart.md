# 快速验证：AI 方案状态三态化与最大延期口径优化

## 1. 前置条件

- 使用仓库现有 Python 虚拟环境和前端依赖。
- 当前功能目录为 `specs/029-ai-status-delay-consolidation`。
- 不修改 `.local.env`，不需要外部 LLM 成功；本地回退方案同样可验证。

## 2. 自动化验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_scheduler.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_plan_control_api.py backend/tests/test_plan_control_repository.py -q
npm.cmd run build
git diff --check
```

预期：全部测试和前端构建通过，无空白错误或契约解析失败。

## 3. 状态矩阵样例

| 样例 | 求解事实 | 预期主状态 | 预期原因 | 排程 |
|---|---|---|---|---|
| 满足目标 | `FEASIBLE`，最大延期 0 | 工期目标已满足 | `target_met` | 保留 |
| 已证明延期 | `OPTIMAL`，最大延期 12 | 工期目标未满足 | `proven_late` | 保留 |
| 限时延期 | `FEASIBLE`，最大延期 12 | 工期目标未满足 | `late_unconfirmed` | 保留 |
| 限时无排程 | `UNKNOWN` | 当前资源未获得可行排程 | `time_limit_no_schedule` | 空 |
| 已证明不可行 | `INFEASIBLE` | 当前资源未获得可行排程 | `proven_infeasible` | 空 |
| 缺少资源 | 资源覆盖失败 | 当前资源未获得可行排程 | `resource_coverage_missing` | 空 |
| 缺少目标 | 有排程、无强制目标 | 无正常主状态 | `target_missing` | 保留 |

## 4. 最大延期样例

输入：

```text
强制里程碑延期 = [0, 12, 5]
固定总工期超期 = 8
```

预期：

```text
max_target_delay_days = 12
hard_milestone_late_days = 17
fixed_duration_overrun_days = 8
页面摘要 = 最大延期 12 天
```

## 5. 页面验证

1. 打开“AI 多方案比选”，生成三方案并分别求解。
2. 验证方案卡和对比表只显示三种新主状态或目标缺失异常，不显示旧四状态名称。
3. 验证延期方案显示“最大延期 X 天”，并能在详情查看逐里程碑延期。
4. 验证已证明延期与限时延期的说明不同，但排程均可查看。
5. 验证只有“工期目标已满足”方案进入推荐。
6. 修改任一资源数量，验证旧主状态、最大延期和推荐立即清空。
7. 将一个有可行排程的方案设为基准，进入“进度反馈与预测”，验证版本和任务正常加载。

## 6. 历史兼容验证

使用临时计划存储分别写入带有 `met`、`not_met`、`unconfirmed`、`infeasible` 的旧快照：

- 查询项目摘要必须成功。
- 页面按回退矩阵显示新主状态和原因。
- 测试前后原文件哈希必须一致。
- 不生成迁移文件或新版本。

## 7. 回归边界

- 单方案仍只执行一次严格固定资源求解。
- 工作量为 0 的工艺资源仍为 0。
- 所有新主状态均不触发自动扩资源。
- 通用“模拟求解”结果和资源建议行为不变。
