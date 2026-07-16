# 快速验证：架梁专项与综合排程融合

本指南用于实现阶段和验收阶段验证 [spec.md](./spec.md) 的端到端闭环。详细字段见 [data-model.md](./data-model.md)，接口见 [contracts/girder-scheduling-api.yaml](./contracts/girder-scheduling-api.yaml)。

## 1. 前置条件

- 已按 `README.md` 安装后端与前端依赖。
- 本地运行使用 Python 3.12 和 Node.js 22 基线。
- 不将真实密钥、`.local-data/` 或旧系统本地状态提交到仓库。
- 实现完成后，`backend/tests/fixtures/girder_planning/` 至少包含：
  - `legacy_parity_single_yard.json`
  - `multi_yard_shared_bridge.json`
  - `same_day_owner_conflict.json`
  - `passage_release_wait.json`
  - `inventory_shortage.json`
  - `rolling_progress_balance.json`
  - `real_project_shadow.json`（可脱敏）

## 2. 静态检查

```powershell
git diff --check
npm.cmd run build
```

预期：

- TypeScript 类型与前端构建通过。
- 新增共享字段在后端模型、前端类型和 API 客户端中一致。
- 未启用 `girder_planning` 的旧场景仍可构建和求解。

## 3. 后端目标测试

```powershell
.\.venv\Scripts\python.exe -m pytest `
  backend\tests\test_girder_planning.py `
  backend\tests\test_integrated_schedule.py `
  backend\tests\test_girder_progress_forecast.py `
  backend\tests\test_plan_control_repository.py `
  backend\tests\test_scheduler.py -q
```

预期：所有测试通过，且原“简支梁不生成任务”的旧断言已被兼容场景和启用专项场景的双分支测试替代。

## 4. 黄金样例验证

### 4.1 未变规则对照

使用 `legacy_parity_single_yard.json`：

- 旧输入先转换为统一项目版本和方案版本。
- 梁场逐日累计产量、库存变化、路线顺序、架梁开始/完成日期和等待原因与已确认旧结果一致。
- 每个差异必须记录对象、旧值、新值和原因；未确认差异导致测试失败。

### 4.2 多梁场与共享桥梁

使用 `multi_yard_shared_bridge.json`：

- 不同梁场并行计算，库存分别记账。
- 同一桥梁可出现在两条启用路线中。
- 最早实际到达路线产生分跨架梁任务并消耗梁片。
- 后续路线产生通道等待/经过记录，不重复生成架梁任务。
- 全局每座待架桥梁的 `ErectionOwnership` 数量恰好为 1。

### 4.3 同日归属冲突

使用 `same_day_owner_conflict.json`：

1. 首次联合计算返回 `blocked`，诊断指出桥梁、竞争路线和同日到达日期。
2. 保存 `owner_override` 后生成新方案版本。
3. 再次计算能够继续，归属来源为 `manual_override`。

### 4.4 通道释放

使用 `passage_release_wait.json`：

- 验证 `passable_date` 等于架后缓冲日期、明确开放日期和关联任务完成日期中的最晚值。
- 后续路线到达早于该日期时必须等待。
- 缺少未确认的架后缓冲时允许专项草稿预览，但阻止专项确认和计划发布。

### 4.5 库存短缺

使用 `inventory_shortage.json`：

- 生产不足时架梁日期顺延，任一天库存均不小于 0。
- 若输入的实绩本身产生负库存或产耗不平衡，返回 `blocked`，不生成未来排程。

## 5. 联合收敛验证

对 `multi_yard_shared_bridge.json` 执行联合计算并检查：

- 每轮包含架梁输入指纹、归属指纹、日期指纹和变化对象。
- 连续两轮的归属与日期完全相同时返回 `converged`。
- 通过测试替身制造 A/B 状态交替时，系统检测到历史指纹重复并提前返回 `not_converged`。
- 通过测试参数制造硬约束无解时返回 `infeasible`。
- 四类终态均包含可定位对象和修复建议。

## 6. API 端到端验证

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

按以下顺序调用契约中的接口：

1. `POST /api/project-data-versions`
2. `POST /api/planning-scenario-versions`
3. `POST /api/girder-planning/validate`
4. `POST /api/girder-planning/preview`
5. `POST /api/planning-scenario-versions/{id}/confirm-specialty`
6. `POST /api/integrated-schedules`
7. `POST /api/plan-control/baselines`

预期：

- 版本号单调递增，输入指纹不匹配返回 409。
- 相同有效输入重复发起联合计算时复用已有快照。
- 只有 `converged`、未失效且专项已确认的联合快照可以发布。
- 发布结果同时包含项目版本、方案版本、联合快照和架梁结果引用。

## 7. 统一发布与失效验证

1. 发布一个已收敛方案。
2. 修改路线、梁场产能或通行参数并保存新方案版本。
3. 尝试使用旧联合快照再次发布。

预期：

- 新方案版本不会修改旧快照。
- 旧快照标记 `stale` 或因指纹冲突被拒绝。
- 不允许只替换架梁结果而沿用旧综合排程结果。

## 8. 实绩与滚动重排验证

使用 `rolling_progress_balance.json`：

1. 对已发布计划保存状态日期实绩，包括累计产量、当前库存、已架分跨、设备位置和通道状态。
2. 生成滚动联合计算。
3. 更正同一状态日期的库存并填写更正原因，再次生成。

预期：

- 状态日期之前的已完成任务、实际日期和实际归属保持不变。
- 只重排状态日期之后的剩余生产、架梁和综合任务。
- 第二次保存生成新修订号，原快照保留且旧预测/联合快照失效。
- 负库存、重复实际架梁或产耗不平衡阻止滚动计算。

## 9. 前端旅程验证

启动开发前端：

```powershell
npm.cmd run frontend:dev
```

在 `http://127.0.0.1:5173/` 完成：

```text
项目数据
  -> 架梁专项策划
  -> 综合排程
  -> 方案比较
  -> 计划发布
  -> 进度与滚动重排
```

核对：

- 无需在两个应用间重复导入或复制数据。
- 架梁专项存在加载、空态、草稿、阻断、警告、已确认和失效状态。
- 综合结果可以定位到路线、桥梁幅别和分跨任务。
- `not_converged`、`infeasible` 和 `blocked` 不显示为成功推荐。
- 输入修改后旧结果和发布按钮立即进入失效/禁用状态。

## 10. 性能与真实项目影子验证

先使用固定性能夹具验证不少于：

- 50 个桥梁幅别节点。
- 300 个架梁分跨。
- 2 个梁场和 2 条启用路线。
- 800 个综合任务。

再对双方确认的脱敏真实项目记录：

- 桥梁、分跨、路线、梁场和任务数量。
- 每轮专项模拟耗时、综合求解耗时和总轮数。
- 最终状态和总耗时。
- 与旧系统未变规则的差异。
- 新规则导致的预期差异。
- 业务确认人、确认日期和剩余问题。

验收目标：上述固定性能夹具在 10 分钟内返回明确终态；黄金样例全部通过；至少一个完整真实项目经业务确认后，取得外部仓库操作授权，将旧系统切换为只读归档、关闭正式入口，并在影子验证记录中保存归档状态与入口关闭证据。

## 11. 全量回归

目标测试通过后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --workspace frontend test
npm.cmd run build
git diff --check
```

实现交付报告必须列出实际执行结果、未覆盖场景、真实项目规模和任何仍需业务确认的差异。

## 12. 本轮实现验证记录

- 后端全量回归：`$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`，328 passed、1 skipped（完整性能基准需显式开启）。
- 架梁专项与联合计算定向测试：`python -m pytest backend/tests/test_girder_models.py backend/tests/test_girder_import.py backend/tests/test_girder_readiness.py backend/tests/test_girder_planning_api.py backend/tests/test_integrated_schedule_api.py -q`，23 passed。
- 前端 Node 测试：`npm.cmd --workspace frontend test -- --run`，21 passed。
- 前端生产构建：`npm.cmd run build`，TypeScript 与 Vite 均通过。
- 架梁实绩导入与滚动预测定向测试：`python -m pytest backend/tests/test_girder_progress_import.py backend/tests/test_progress_forecast.py -q`，42 passed。
- 固定性能夹具：`$env:PYTHONPATH='backend'; $env:RUN_GIRDER_PERFORMANCE='1'; python -m pytest backend/tests/test_girder_performance.py -q -s`，2 passed；800 个综合任务、300 个分跨，适配 0.12 秒、总耗时 65.32 秒，终态 `FEASIBLE`。
- 当前已验证：项目/方案版本确认、桥梁幅别导入、共享桥梁唯一归属、供梁库存、通行释放、分跨架梁任务、联合快照、统一基线门禁、架梁实绩 Excel/CSV 解析和状态日联合滚动预测。
- 尚未验证：真实项目新旧影子对照；旧系统只读归档和正式入口关闭。固定性能夹具已在本地受控环境完成，但尚未替代真实项目验收。
