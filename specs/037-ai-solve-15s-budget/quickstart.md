# 快速验证：AI 单方案 15 秒求解预算

## 1. 验证目标

- 每套 AI 固定资源方案只调用一次排程。
- 唯一阶段配置 15 秒最大时限。
- 三套方案分别独立获得 15 秒。
- 不改变目标、资源、状态、诊断和非 AI 入口。

## 2. 后端针对性验证

```powershell
python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q -k "time_limit or exact_resources"
python -m pytest backend/tests/test_scheduler.py -q -k "ai_single_stage"
```

核心断言：

- 服务端默认求解时限为 `15.0`；
- `total_budget_seconds=15.0`；
- `primary.configured_budget_seconds=15.0`；
- `target_achievement.time_budget_seconds=15.0`；
- `solver_call_count=1`；
- `secondary.attempted=false`；
- `resource_expansion_attempted=false`。

## 3. 前端验证

```powershell
cd frontend
npm.cmd run build
```

页面检查：

- 顶部说明为“单方案固定资源求解最长 15 秒”；
- 不出现当前 60 秒说明；
- 新结果仍只显示工期求解事实；
- 历史结果仍可打开。

## 4. 真实 Excel 三方案验证

1. 默认导入 `渠溪河特大桥结构设计表.xlsx`。
2. 使用本地回退或同一份 LLM 输出生成经济、平衡、抢工三方案。
3. 串行求解三套方案。
4. 记录每套方案的预算、实际耗时、调用次数、状态、总工期、最大延期、资源快照和诊断。
5. 断言三套方案均配置 15 秒、只调用一次且未自动增配。

## 5. 完整回归

```powershell
python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py backend/tests/test_bridge_import.py -q
cd frontend
npm.cmd run build
```

预期：预算传播、单阶段、历史兼容、默认 Excel 导入、完整排程和前端构建全部通过。
