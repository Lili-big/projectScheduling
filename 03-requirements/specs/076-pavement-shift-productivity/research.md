# 研究结论：076-pavement-shift-productivity

日期：2026-09-29。阻塞性未知项在计划前已全部消除，无遗留"需澄清"。

## R1 CP-SAT 变量工期的建模方式

**问题**：`Task.duration_days` 当前是常量，CP-SAT 区间、机组路径 `AddCircuit`、`NoOverlap` 都直接使用它；班制下工期依赖开始日期，如何在不改求解架构的前提下变量化？

**结论**：采用**每任务预计算工期表 + 表约束**：
- 建模前对每个任务预计算 `duration_by_start = [f(i) for i in 0..horizon]`（`f` 为 spec FR-003 工期函数，horizon 沿用现有公式）；
- `dvar = NewIntVar(min(f), max(f))`；`AddAllowedAssignments([starts[tid], dvar], [(i, f(i)) for i in 0..horizon])`；`ends == starts + dvar`；
- `NewOptionalIntervalVar` 直接接受 `dvar`，`AddCircuit`/`NoOverlap` 语义不变；
- warm start 对 `dvar` hint `f(initial.starts[tid])`。

**依据**：本仓库 `.venv` 实测 OR-Tools 9.15.6755 `AddAllowedAssignments` 可用。规模评估：客户量级 horizon 约数百，100 任务 × 数百行 ≈ 数万表行，CP-SAT 表约束为常规量级；预计算在建模期一次完成，不进搜索循环。

**已评估替代方案**：
- 按"边界前开工/后开工"布尔分支约束：跨界段工期仍随开始日连续变化（每天开工的跨界工期都不同），分支数不可控，放弃；
- 表约束换成 `AddElement` 间接寻址：语义等价，表约束更直读且无额外中间变量，选表约束。

**关键不变量**：horizon 公式不需要变化——双班只可能缩短工期，`duration_days`（单班基准）仍是每任务工期上界，现有 horizon（各任务基准工期之和 + lag + 转场）继续覆盖最坏情形。

## R2 工期函数的浮点确定性与"最少 1 天"

**问题**：`productivity_value`、`quantity` 均为 float，FR-003 的逐日累计存在浮点求和误差；剩余量极小时的天数取整口径必须唯一。

**结论**：唯一实现在 `scheduling/domain/shift_regime.py`：
- 逐日累计用 float 求和，判满条件 `accumulated >= quantity - 1e-9`（容差吸收浮点误差，保证同输入必同输出）；
- `k` 从 1 起（先累计再判断），天然满足"最少 1 天"；
- 空班制列表时函数直接返回 `task.duration_days`，与 `calculate_duration` 的基准值一致——这是 FR-005 逐位一致的机制保证（同一代码路径，不是平行实现）。

**依据**：现有 `calculate_duration`（`wbs.py`）与 `validate_candidate`（`pavement_heuristic.py:92`）均以整数天与精确相等判定，容差只新增在班制累计路径上，空配置路径不受影响。

## R3 契约放置与指纹失效

**问题**：班制配置放哪一层才能让 069 实时求解、074 窝工基准指纹、任务预览都自然生效？

**结论**：
- `PavementShiftRegime` 定义在 `contracts/pavement.py`；`PavementSettings.shift_regimes: list[PavementShiftRegime] = []`（用户配置入口，随既有保存链路持久化）；
- `ScheduleInput.shift_regimes: list[PavementShiftRegime]`（`default_factory=list` + 空列表 `exclude_if`，仿照 `readiness_conditions` 的既有风格）：生成时从 settings 快照，进入 `schedule_fingerprint` 全量指纹 → 班制变更后旧结果自动失效为"历史结果"，074 基准校验（`PAVEMENT_BASELINE_OUTDATED`）同样自动生效，无需新增失效机制；
- 领域分派与兼容：桥梁请求不经过该字段（生成层仅路面写入）；旧请求省略该字段 = 空列表 = 现状行为；架构基线（backend/frontend fixture）与 Netlify 镜像 `api.mts` 在实施时同步重新捕获。

**依据**：`ScheduleInput` 现有 `readiness_conditions`/`pavement_handover_scope` 已采用同样的可选快照 + `exclude_if` 模式（`contracts/_models.py:1038` 起）；`schedule_fingerprint` 对 `schedule_input` 全量 `model_dump`（`strategies/pavement.py:537`）。

## R4 各消费方对"函数工期"的适配点盘点

对求解链路逐点核对（grep `duration_days` 共 9 处直接引用）：

| 位置 | 现状用法 | 改造 |
| --- | --- | --- |
| `strategies/pavement.py:_build_model` `ends == starts + duration_days`、interval | 常量 | `dvar` + 表约束（R1） |
| `constraints/pavement.py` interval duration 参数 | 接收常量 | 改收 `dvar`（调用侧变化，约束本体不变） |
| `pavement_heuristic.py:validate_candidate` `e != s + duration_days` | 常量复核 | 改用工期函数 |
| `pavement_heuristic.py:construct_candidate` `e = s + duration_days`、chain 链长 | 常量构造 | 改用工期函数（chain 用基准工期作启发式即可，不追求精确） |
| `strategies/pavement.py:result_from_candidate` `ScheduledTask(**task.model_dump(), ...)` | 日期换算 | 不变（end 已是实际值）；新增单/双班拆分输出 |
| `strategies/pavement.py:horizon` 求和 | 基准工期上界 | 不变（R1） |
| 前置约束、ready、milestone、idle `idle_metrics` | 基于 starts/ends | 不变 |

074 窝工优化：`validate_idle_baseline` 中"基准任务时刻/工期有效性"校验改用同一工期函数；`idle_metrics` 基于实际 starts/ends 无需改动。

**结论**：适配面收敛在 3 个后端文件 + 1 个新领域模块；预览（066）与前端任务表继续显示 `duration_days` 基准值，符合 spec 默认假设。

## R5 前端编辑器与拆分展示的落点

- 班制编辑器：`features/logic/LogicTab.tsx` 已持有 `onUpdatePavementSettings` 通道（`Workspace.tsx:5289`），班制区间行编辑（起/止/班次、增删）并入路面设置区，不新增 feature 目录；
- 拆分展示：前端 `domain/pavement.ts` 增加与后端同公式的纯函数（由结果 `start_offset/end_offset` + `schedule_input.shift_regimes` 推导单/双班天数），任务详情（taskView）与 `PavementPlanTimeline` 双班区间标注消费它；公式一致性由前后端各自 Node/pytest 测试用 SC-001 同一数值样例锁定；
- 历史结果提示：依赖 R3 指纹机制，前端零改动。

## R6 错误码与校验位置

班制配置校验落在两处（直接 `/solve` 载荷与生成载荷都必须受控，与既有"双层校验"模式一致）：
- 生成层 `generation/pavement.py`：`PAVEMENT_SHIFT_INVALID`（起>止、同起点重复、区间重叠）；
- 求解层 `strategies/pavement.py:validate_pavement_schedule`：同一规则复算（日期格式由 Pydantic `date` 类型在契约层拦截）。
错误码统一 `PAVEMENT_SHIFT_` 前缀（spec FR-002）。
