# 快速验证：第二阶段可见墩距路径剪枝

> 当前实现校正（2026-07-08）：该剪枝规则已由 `017-stage1-route-continuity` 前移到第一阶段空间路径候选；常规自动流程不再运行第二阶段剪枝。本 quickstart 只作为历史兼容或显式二阶段诊断路径的验证参考。

## 验证命令

```powershell
python -m pytest backend/tests/test_scheduler.py -k "sparse_arcs or visible_support_distance"
python -m pytest backend/tests/test_scheduler.py
```

## 期望结果

- 第一阶段路径候选诊断体现同幅窗口和跨幅窗口规则。
- 历史二阶段显式诊断路径如仍被调用，候选弧数量体现跨幅窗口为 1。
- 全量后端排程测试通过。
