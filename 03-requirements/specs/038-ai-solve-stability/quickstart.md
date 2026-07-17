# 快速验证：AI 固定资源排程结果稳定化

## 前置条件

- 使用仓库根目录 `渠溪河特大桥结构设计表.xlsx`。
- AI 方案使用严格固定资源单阶段求解，单方案配置时限为 15 秒。
- 不依赖外部 LLM，重复测试可使用固定资源方案构造。

## 场景 1：真实 Excel 首次求解收敛

1. 导入真实 Excel，确认结构物 50、任务 351。
2. 固定平衡方案资源量：旋挖钻 10、承台模板 5、墩柱模板 10、盖梁模板 5、连续梁班组 2，其余桩基工艺资源为 0。
3. 每次不携带上一版结果，独立重复求解至少 5 次。
4. 核对每次资源数量、求解调用数、15 秒配置、最大目标延期和总工期。

预期：资源快照完全一致，自动增配为 0；首次样例总工期最大值与最小值差不超过 30 天；可行解仍如实标记是否已证明最优。

## 场景 2：同输入重复求解只改进不退化

1. 完成一次可行求解并保留响应。
2. 将该响应作为 `previous_plan_result` 连续重新求解至少 5 次。
3. 按 `(最大目标延期, 总工期)` 记录每次最终结果。

预期：序列单调不增；本轮更差或无排程时最终结果保持上一版，并记录 `current_worse` 或 `current_no_schedule`。

## 场景 3：已证明最优结果复用

1. 准备同输入 `OPTIMAL` 旧结果。
2. 再次提交单方案请求。

预期：直接保留旧结果，`selection_reason=previous_optimal_reused`，本次 `solver_call_count=0`。

## 场景 4：输入变化失效

1. 完成一次求解并保留结果。
2. 分别修改资源数量、里程碑日期和项目任务来源后提交旧结果。

预期：每次旧结果均被拒绝，不作为 warm start 或兜底；本轮独立求解，诊断说明指纹不匹配。

## 场景 5：不完全可互换资源

1. 构造同类型但日历或兼容任务不同的两台资源。
2. 生成排程模型并求解。

预期：两台资源不进入同一可互换组，不新增会删除业务可行解的顺序约束。

## 自动验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_resource_scheduling_assistant.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_plan_control_api.py -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

## 页面验证

- 同一方案再次求解时，结果只改善不退化。
- 本轮未改善时显示保留上次较优排程的说明。
- 修改资源后旧结果和稳定性说明立即失效。
- 推荐、设为基准计划和进度反馈继续读取最终保留结果。
