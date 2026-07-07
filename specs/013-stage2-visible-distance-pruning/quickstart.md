# 快速验证：第二阶段可见墩距路径剪枝

## 验证命令

```powershell
python -m pytest backend/tests/test_scheduler.py -k "sparse_arcs or visible_support_distance"
python -m pytest backend/tests/test_scheduler.py
```

## 期望结果

- 全量左右幅 1#-6# 样例通过，候选弧数量体现跨幅窗口为 1。
- 只有 1# 和 4# 候选任务的样例通过，说明距离使用可见候选序列。
- 全量后端排程测试通过。
