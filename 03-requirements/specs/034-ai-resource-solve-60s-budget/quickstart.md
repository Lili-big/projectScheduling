# 快速验证：AI 两阶段排程共享 60 秒预算

## 前置条件

- 使用仓库现有 Python、Node.js 和依赖环境。
- 保留当前工作区未提交修改，不重写 033 的实现和真实 Excel 基线。
- 真实验证使用根目录 `渠溪河特大桥结构设计表.xlsx`，三套方案必须复用同一份 LLM 资源快照并串行运行。

## 1. 后端预算传播验证

```powershell
python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py -q
```

预期：

- 默认 AI 单方案输入的 `time_limit_seconds=60.0`；
- `optimization_stages.total_budget_seconds=60.0`；
- 第一阶段配置预算为 60.0，第二阶段配置预算大于 0 且不超过剩余预算；
- 短预算隔离用例仍可通过 monkeypatch 验证跳过第二阶段，而不必真实等待 60 秒；
- 固定资源数量不变且 `resource_expansion_attempted=false`；
- 目标、状态和回退测试保持通过。

## 2. 兼容与完整回归

```powershell
python -m pytest backend/tests/test_plan_control_repository.py backend/tests/test_plan_control_api.py backend/tests/test_progress_forecast.py -q
python -m pytest backend/tests -q
```

预期：

- 历史 30 秒阶段摘要及无阶段摘要的基准计划仍可加载；
- 设为基准、进度反馈和预测链路不变；
- 通用模拟求解、资源成本及最少资源入口不受影响。

## 3. 前端生产构建

```powershell
Set-Location frontend
npm.cmd run build
```

预期：构建通过，AI 多方案比选页面显示“单方案两阶段共享 60 秒预算”，不出现“每阶段各 60 秒”的误导表述。

## 4. 真实 Excel 三方案验证

1. 导入 `渠溪河特大桥结构设计表.xlsx`。
2. 生成一次经济、平衡、抢工三套 LLM 资源方案并固定资源快照。
3. 串行求解三套方案，不与全量测试或其他 CP-SAT 运行并行。
4. 记录每案的资源数量、第一阶段状态/工期、第二阶段状态、最终工期、最大延期、空闲、连续性、选择阶段、回退原因、阶段配置时限及总耗时。

30 秒基线：

| 方案 | 固定资源摘要（旋挖/承台/墩柱/盖梁/连续梁） | 30 秒最终工期 | 30 秒最终空闲/连续性 |
|---|---|---:|---:|
| 经济 | 8/4/8/4/1 | 939 天 | 1076 / 926 |
| 平衡 | 10/5/10/5/2 | 579 天 | 935 / 855 |
| 抢工 | 10/9/10/9/2 | 579 天 | 416 / 708 |

必须核对：

- 三案分别返回 `total_budget_seconds=60.0`；
- 回旋钻、冲击钻、人工挖孔工作量为 0 时资源仍为 0；
- 所有资源快照与求解输入一致，自动增配次数为 0；
- 最终工期优先不劣于 939/579/579 天基线；如单次结果受求解器非确定性影响，使用相同输入重放并保留第一阶段与回退诊断，禁止通过增加资源修正；
- 第二阶段被选用时，工期不退化且次目标向量严格改善；未选用时完整返回第一阶段排程和原因。

## 5. 差异检查

```powershell
git diff --check
git diff -- backend/app/services/ai_resource_scheduling_assistant.py backend/app/scenario.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx docs/AI资源配置与排程优化助手验证说明.md specs/034-ai-resource-solve-60s-budget
```

预期：只出现 AI 默认预算、对应断言、页面说明、验证文档和 034 Spec Kit 产物变化；LLM 超时、通用求解时限、目标函数和资源数量逻辑无差异。

## 6. 2026-07-14 真实 Excel 实测证据

实际导入根目录 `渠溪河特大桥结构设计表.xlsx`，得到 50 个结构物、351 个任务。首次运行真实调用当前 DeepSeek 配置，返回 `source=llm`、`validation_status=partially_valid`；该次 LLM 推荐的资源数量与 033 基线明显不同，例如经济方案旋挖钻由 8 台变为 1 台、抢工方案由 10 台变为 3 台，因此不能把其工期差异归因于求解时限。

为严格隔离“30 秒改为 60 秒”的影响，随后固定 033 已记录的同一份真实 LLM 资源快照，串行重放三案。结果如下：

| 方案 | 旋挖/承台/墩柱/盖梁/连续梁 | 第一阶段状态/工期 | 第一阶段空闲/连续性 | 第二阶段状态 | 最终工期 | 最终空闲/连续性 | 选择阶段 | 两阶段耗时 |
|---|---|---|---|---|---:|---|---|---:|
| 经济 | 8/4/8/4/1 | OPTIMAL / 939 天 | 2035 / 1078 | FEASIBLE | 939 天 | 671 / 1075 | secondary | 58.785 秒 |
| 平衡 | 10/5/10/5/2 | OPTIMAL / 579 天 | 1150 / 969 | FEASIBLE | 579 天 | 409 / 852 | secondary | 58.986 秒 |
| 抢工 | 10/9/10/9/2 | OPTIMAL / 579 天 | 1862 / 792 | FEASIBLE | 579 天 | 719 / 788 | secondary | 62.279 秒 |

核查结论：

- 三案 `optimization_stages.total_budget_seconds=60.0`，第一阶段配置预算均为 60 秒，第二阶段只使用第一阶段结束后的剩余预算。
- 三案最大延期均为 0，最终工期保持 939/579/579 天，不劣于相同资源快照的 30 秒基线。
- 三案第二阶段均严格降低资源空闲，并在资源空闲改善后同步降低连续性罚分；第二阶段均为 `FEASIBLE`，不改变第一阶段已经证明的工期最优结论。
- 三案 `solver_call_count=2`、`resource_expansion_attempted=false`；回旋钻、冲击钻、人工挖孔工作量为 0，对应资源数量保持 0。
- 抢工方案端到端阶段墙钟耗时比 60 秒多 2.279 秒，来自模型构建和结果组装固定开销；两个 CP-SAT 阶段没有各自获得 60 秒。
- CP-SAT 多线程搜索存在非确定性，因此同一工期下的第一阶段空闲和连续性诊断可能与 033 单次运行不同；本次采用规则仍严格保证第二阶段工期不退化且次目标向量改善。
