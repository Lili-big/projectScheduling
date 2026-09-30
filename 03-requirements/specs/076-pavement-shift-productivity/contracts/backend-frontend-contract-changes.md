# 契约变更清单：076-pavement-shift-productivity

日期：2026-09-29。本文件列出前后端/镜像必须同步的每一处契约变化；字段定义见 [data-model.md](../data-model.md)。

## 1. 后端 Pydantic 模型（权威）

| 位置 | 变更 |
| --- | --- |
| `04-demo/backend/app/contracts/pavement.py` | 新增 `PavementShiftRegime`（`start_date`/`end_date: date \| None`/`shifts: int ∈ [1,2]`，含起止顺序 model_validator） |
| `04-demo/backend/app/contracts/pavement.py` | `PavementSettings` 新增 `shift_regimes: list[PavementShiftRegime] = []` |
| `04-demo/backend/app/contracts/_models.py` | `ScheduleInput` 新增 `shift_regimes`（空列表 `exclude_if`） |

- 兼容：全部为新增可选字段，旧载荷不发送即取默认；旧结果反序列化不受影响。
- 状态码/错误 detail 结构不变；新增校验错误走既有 `ValidationMessage`（`level="error"`，`code="PAVEMENT_SHIFT_INVALID"`），不新增 HTTP 状态语义。

## 2. API 端点（无路径/方法/状态码变化）

`/api/generate-schedule-input`、`/api/solve-scenario`、`/api/solve-scenario/stream`、`/api/solve-scenario/idle/stream` 的请求/响应 schema 因新字段扩展；OpenAPI 基线重新捕获：

```text
04-demo/backend/tests/fixtures/architecture/backend-baseline.json
```

（实施时用 `capture_architecture_baseline.py` 重新生成，经 `verify:architecture` 门禁核对。）

## 3. 前端类型（镜像）

| 位置 | 变更 |
| --- | --- |
| `04-demo/frontend/src/contracts/scheduler.ts` | 新增 `PavementShiftRegime`；`PavementSettings`/`ScheduleInput` 对应字段 |
| `04-demo/frontend/src/domain/pavement.ts` | 新增与后端同公式的 `shiftsForDay`/`taskDurationForStart`/`splitShiftDays` 纯函数 |

前端架构基线 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 同步重新捕获。

## 4. Netlify 参考镜像

`04-demo/tools/demo-api-mirror/api.mts`：同步 `ScheduleInput`/`PavementSettings` schema 表达（既有测试断言镜像与端点一致）。

## 5. 事件流（不变）

`PavementSolveStarted/Solution/Complete/Error`（`contracts/pavement_stream.py`）结构不变；`ScenarioSolveResult.generated.schedule_input` 内自然携带 `shift_regimes`，无需新增事件字段。

## 6. 下游失效行为

- 班制配置变更 → 保存 → 重新生成/求解：`schedule_fingerprint` 变化 → 页面"历史结果"提示（既有机制）；
- 074 窝工优化：基准 `pavement_summary.input_fingerprint` 与新指纹不一致 → 422 `PAVEMENT_BASELINE_OUTDATED`（既有机制，自动覆盖）；
- 无新增失效代码路径。
