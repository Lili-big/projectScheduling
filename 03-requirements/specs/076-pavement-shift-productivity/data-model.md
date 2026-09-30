# 数据模型：076-pavement-shift-productivity

日期：2026-09-29。仅列本功能新增/变更的实体与字段；既有实体不重复。

## 新增实体

### PavementShiftRegime（班制区间）

一段连续日期上的班制声明。定义于 `04-demo/backend/app/contracts/pavement.py`，前端镜像类型于 `04-demo/frontend/src/contracts/scheduler.ts`。

| 字段 | 类型 | 约束 | 语义 |
| --- | --- | --- | --- |
| `start_date` | `date` | 必填 | 区间起始日（含当日） |
| `end_date` | `date \| None` | 可空；非空时须 ≥ `start_date` | 区间结束日（含当日）；`None` 表示延续至计划期末 |
| `shifts` | `int` | `1 <= shifts <= 2` | 该区间内每日班次数：1=单班，2=双班 |

校验规则（spec FR-002，错误码 `PAVEMENT_SHIFT_INVALID`）：

- `start_date <= end_date`（非空时）；
- 列表内 `start_date` 不得重复；
- 任两区间不得重叠（按 [start, end] 闭区间判定，`None` 视为 +∞）；
- 日期格式由 Pydantic `date` 在契约层拦截；
- 区间列表之外的日期班制恒为 1（未覆盖默认单班）；显式配置 `shifts=1` 区间合法但冗余。

## 变更实体

### PavementSettings（`contracts/pavement.py`）

新增字段：

```text
shift_regimes: list[PavementShiftRegime] = []   # 项目级班制区间；空列表 = 全程单班（现状）
```

随既有路面设置保存链路持久化（本地场景配置），无独立存储。

### ScheduleInput（`contracts/_models.py`）

新增字段：

```text
shift_regimes: list[PavementShiftRegime] = Field(default_factory=list, exclude_if=lambda value: not value)
```

- 任务生成时从 `PavementSettings.shift_regimes` **快照**写入（求解只读 ScheduleInput，不回读 settings）；
- 进入 `schedule_fingerprint` 全量指纹：班制变更 → 既有结果自动失效为"历史结果"，074 窝工基准报 `PAVEMENT_BASELINE_OUTDATED`；
- 空列表在序列化中省略（仿 `readiness_conditions` 既有风格），旧载荷/旧结果兼容；
- 桥梁领域生成路径不写入该字段，行为不变。

### Task（不变，语义澄清）

`duration_days` 语义保持**单班基准工期**（= 现状 `calculate_duration` 结果），不新增字段：

- 是任务预览（066）与任务表展示口径；
- 是 horizon 计算的每任务上界（双班只缩短工期）；
- 实际工期 = `工期函数(start_offset)`（下节），由求解与复核层计算，结果层输出实际 start/end。

## 领域函数（新增，唯一权威实现）

`scheduling/domain/shift_regime.py`（前端镜像于 `domain/pavement.ts`）：

```text
shifts_for_day(regimes, day_date) -> 1 | 2
    未覆盖日期返回 1。

task_duration_for_start(task, start_offset, regimes, start_date) -> int
    FR-003：k = 最小整数 k>=1 使 Σ(i=0..k-1) v * shifts_for_day(start+i) >= quantity - 1e-9；
    regimes 为空时返回 task.duration_days（逐位一致路径）。

split_shift_days(task, start_offset, end_offset, regimes, start_date) -> (单班天数, 双班天数)
    结果展示用；对 [start, end) 逐日按 shifts_for_day 计数，与 task_duration_for_start 同源口径。
```

## 状态与失效

- 班制配置无独立状态机；配置变更 = 保存场景配置（既有 dirty/save 流程）。
- 结果失效：`schedule_fingerprint` 覆盖 `shift_regimes` → 页面既有"历史结果"提示与 074 基准失效自动生效，无新机制。

## 结果输出（展示口径）

- `ScheduledTask`：不新增字段；前端按 `split_shift_days` 推导拆分；
- `PavementSummary.resource_assumptions`：追加一条班制说明文案（说明区间与未覆盖日期按单班处理，spec FR-008）。
