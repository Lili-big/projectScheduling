# 快速验证：resource_path_continuity 候选路径无窗口化

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## 前置条件

- 已安装项目 Python 依赖和 OR-Tools。
- 在仓库根目录执行验证命令。
- 用户已确认本规格、任务和分析结果后再进入实现。

## 验证 1：机械桩基仍聚合为钻机组节点

**场景**：同一结构物内存在多根旋挖、冲击或回旋桩基，资源连续性开启。

**期望**：
- 同结构物内多根机械桩基只形成 1 个钻机组节点。
- 最终结果仍输出原始桩基任务 ID。
- `drill_group_refinement.status` 保持当前第一阶段最终排程语义。

## 验证 2：同幅远距离候选被允许

**场景**：同幅可施工墩组为 `[1, 2, 4, 7]`，资源连续性开启。

**期望**：
- `1# -> 2#` 罚分为 0。
- `1# -> 4#` 被允许，罚分为 0。
- `1# -> 7#` 被允许，罚分为 0。
- 4 个节点的一台资源候选有向弧数为 12。
- `same_side_window_exceeded` 计数为 0。

## 验证 3：跨幅远距离候选被允许

**场景**：左幅 `1#` 和右幅 `4#` 均为同一机械钻资源可施工钻机组。

**期望**：
- 该跨幅转移被允许。
- `cross_side_support_gap = 3`。
- 跨幅顺序罚分为 0。
- `cross_side_gap_exceeded` 计数为 0。

## 验证 4：旧窗口不可行样例更新

**场景**：旧测试中只有远距离跳转才能形成顺序路径。

**期望**：
- 系统不再因 `stage1_route_window_infeasible` 失败。
- 若其他硬约束允许，应返回可行排程。
- 诊断体现候选模式为无窗口或等价语义。

## 验证 5：目标关闭和回归

**场景**：关闭 `resource_path_continuity`。

**期望**：
- 第一阶段路径状态为 `not_enabled` 或等价未评估语义。
- 节点数、候选弧数和顺序罚分为 0。
- 其他硬约束继续生效。

## 建议命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -k "stage1_route or mechanical_drill"
```

完整后端回归：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py
```

如实现涉及前端类型或展示，再执行：

```powershell
npm.cmd run build --prefix frontend
```

## 本轮验证记录（2026-07-09）

- 已运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -k "stage1_route or mechanical_drill or drill_group or resource_path_continuity" -q`，结果：25 passed。
- 已运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q`，结果：158 passed。
- 已运行 `.\.venv\Scripts\python.exe backend\scripts\run_excel_case_solve.py --mode fixed-resource --output logs\excel-case-solve-fixed-resource-latest.json`，结果：`status = UNKNOWN`、`schedule_source = target_unconfirmed`、`target_status = unconfirmed`；诊断已更新为“候选路径已按无顺序罚分模式进入模型”，未出现 `stage1_route_window_infeasible` 或“未放开远距离候选转移”旧窗口语义。
- 本次未修改 `frontend/src/types/scheduler.ts` 或 `frontend/src/app/App.tsx` 的诊断解析逻辑，因此未运行前端构建。
