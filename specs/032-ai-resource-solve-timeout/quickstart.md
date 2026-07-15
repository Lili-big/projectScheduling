# 快速验证：AI 资源方案求解时限调整

## 前置条件

- 项目依赖已安装。
- 本地 FastAPI 服务使用当前代码启动。
- 真实样例 `渠溪河特大桥结构设计表.xlsx` 可读取。
- 外部 LLM 可用或允许使用本地三方案回退；两者均可验证求解预算。

## 自动化验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_resource_scheduling_assistant.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
npm.cmd run build
```

重点断言：

- 单方案和批量方案进入严格求解时均使用 `time_limit_seconds=30.0`。
- `solver_call_count=1`。
- `resource_expansion_attempted=false`。
- 方案资源数量与命名资源数量一致。
- 默认场景和非 AI 入口仍保留原有 15 秒行为。

## 真实 Excel 验证

1. 导入 `渠溪河特大桥结构设计表.xlsx`。
2. 进入“AI 多方案比选”，生成经济、平衡、抢工三套方案。
3. 至少点击一套方案的求解按钮；完整验收时依次求解三套方案。
4. 核查响应：
   - `generated.schedule_input.time_limit_seconds=30.0`；
   - `stats.configured_time_limit_seconds=30.0`；
   - `stats.target_achievement.time_budget_seconds=30.0`；
   - `stats.solver_call_count=1`；
   - `resource_expansion_attempted=false`。
5. 记录求解器状态、实际耗时、总工期和最大延期。若状态仍为 `FEASIBLE`，只说明尚未证明最优，不把它视为功能失败。

## 回归边界

- 通用“模拟求解”的场景时限输入与最大值不变。
- 最少资源和资源成本求解不使用本功能的 30 秒专项预算。
- LLM 生成内容、三方案资源数量、目标函数和权重不变。
