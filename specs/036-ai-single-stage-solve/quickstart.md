# 快速验证：AI 固定资源单阶段求解

## 1. 验证目标

- 每套 AI 资源方案只调用一次排程。
- 唯一阶段使用完整 60 秒最大预算。
- 目标保持最大延期优先、总工期其次。
- 不执行资源空闲第二阶段。
- 诊断、历史结果和下游链路保持兼容。

## 2. 后端针对性测试

```powershell
python -m pytest backend/tests/test_scheduler.py -q -k "ai and single_stage"
python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q
python -m pytest backend/tests/test_plan_control_api.py -q
```

核心断言：

- `solver_call_count == 1`；
- 唯一调用的 `optimization_stage == "primary"`；
- 唯一阶段配置预算为 60 秒；
- `secondary.attempted == false`；
- `secondary.skipped_reason == "not_applicable"`；
- `selected_stage == "primary"`；
- `resource_expansion_attempted == false`。

## 3. 目标与诊断小样例

构造固定资源排程：

- 强制里程碑最大延期 5 天；
- 总工期 900 天；
- 最终排程累计资源空闲 120 天；
- 连续性诊断罚分 80。

预期：

- 结果直接返回最大延期 5 天和总工期 900 天；
- 资源空闲和连续性只进入诊断；
- 不因诊断值触发第二次求解或改变状态。

## 4. 前端验证

```powershell
npm.cmd run build
```

页面检查：

- 顶部不再显示两阶段共享预算；
- 新方案卡只显示工期求解状态；
- 不显示第二阶段未执行或回退提示；
- 历史两阶段结果仍可打开；
- 资源或场景变化后旧结果和推荐立即失效。

## 5. 真实 Excel 三方案验证

1. 默认导入 `渠溪河特大桥结构设计表.xlsx`。
2. 生成经济、平衡、抢工三套资源方案。
3. 分别点击求解。
4. 记录每套方案的调用次数、配置预算、实际耗时、总工期、最大延期、固定资源数量和诊断。
5. 验证三套方案均只调用一次且无自动增配。

## 6. 完整回归

```powershell
python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py backend/tests/test_bridge_import.py -q
npm.cmd run build
```

预期：新单阶段测试、历史兼容、默认 Excel 导入、完整排程和前端构建全部通过。
