# Quickstart：统一固定资源与最少资源求解

## 目标

在实施 056 后，用最少的一组可复现检查证明：

1. 模拟与 AI 固定资源入口共用一阶段算法；
2. 固定工期只有一次全局搜索和一次详细排程；
3. 详细结果失败后不增配、不回退、不重试；
4. 搜索下限为 0，页面和契约准确表达新语义；
5. 单工点、历史结果与其他求解入口不回归。

所有命令从仓库根目录 `D:\codex_workspace\排程算法` 执行。

## 1. 静态契约检查

```powershell
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path(r'03-requirements/specs/056-unified-fixed-resource-solve/contracts/unified-fixed-resource-solve.openapi.yaml').read_text(encoding='utf-8')); print('contract ok')"
```

预期：输出 `contract ok`。如果本地没有 PyYAML，由后端 OpenAPI/契约测试代替，不为本功能新增依赖。

## 2. 固定资源共享内核

运行定向 application、AI 与目标测试：

```powershell
python -m pytest 04-demo/backend/tests/scheduling/test_fixed_resource_application.py 04-demo/backend/tests/test_ai_resource_scheduling_assistant.py 04-demo/backend/tests/scheduling/test_solver_objectives.py -q
```

至少验证：

- 相同 `ScheduleInput` 与资源数量经模拟和 AI 入口得到相同目标顺序及四态判定；
- 每个入口的 `solver_call_count == 1`；
- `resource_expansion_attempted == false` 且 `alternative_results == []`；
- 实际展开的命名资源数量严格等于输入 `quantity`，数量 0 不静默补足；
- `objective_priority == [max_target_delay_days, makespan_days]`；
- 资源空闲/连续性仍有诊断，但对应 modeling gate 不参与目标；
- `OPTIMAL+延期 -> not_met`、`FEASIBLE+延期 -> unconfirmed`；已有排程不丢失。

## 3. 全局最少资源与一次详细排程

```powershell
python -m pytest 04-demo/backend/tests/scheduling/test_resource_search_application.py 04-demo/backend/tests/test_scheduler.py -q -k "min_resource or minimum_resource or unified_fixed"
```

至少验证：

- 一次请求只调用一次全局 `_solve_capacity_model`；
- 全局候选存在时只调用一次共享固定资源详细排程；
- 默认 `search_lower_bounds` 全为 0，可返回低于当前 `quantity` 的推荐数量；
- 资源总数为主目标，同总数下总工期为第二目标；
- 全局 `UNKNOWN/INFEASIBLE` 不调用最大资源预检、逐池二分、压力或详细排程；
- 详细 `not_met/unconfirmed/infeasible` 时 `candidate_verified == false`，候选仍返回，重试次数为 0；
- 详细 `met` 时 `candidate_verified == true`。

## 4. API、范围和 AI 推荐门禁

```powershell
python -m pytest 04-demo/backend/tests/test_scheduling_routes.py 04-demo/backend/tests/scheduling/test_single_workpoint_solve.py 04-demo/backend/tests/test_ai_workpoint_resource_comparison.py 04-demo/backend/tests/test_contracts_scheduling.py -q
```

预期：

- 三个现有 API 路径和请求主体保持有效；
- `workpoint_id` 继续只影响范围，不改变算法；
- 固定工期 fallback 只复用同范围、同指纹固定资源工期；
- 只有 `met` 的 AI 方案可进入推荐；
- 单工点结果仍不能保存为全项目方案或混入全项目比较。

## 5. 前端目标与结果展示

```powershell
npm.cmd --workspace 04-demo/frontend test -- --test-name-pattern="solve|objective|resource"
npm.cmd run typecheck
npm.cmd run build
```

预期：

- 固定资源/固定工期页面显示只读目标顺序，不提供资源空闲/连续性优化开关；
- 资源空闲与连续性只在诊断结果中出现；
- 固定工期把候选数量、详细状态和验证状态分开显示；
- 历史多阶段结果仍可读取并按历史来源展示；
- TypeScript 类型检查与 Vite 生产构建通过。

## 6. Demo API 镜像兼容

```powershell
node --test 04-demo/frontend/tests/apiCompatibility.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs 04-demo/frontend/tests/deploymentContract.test.mjs
```

预期：镜像路径与字段兼容，fixture 不再把固定资源结果表达为自动增配/方案 2，也不把容量候选状态冒充详细排程成功。

## 7. 关键手工样例

### 样例 A：同输入跨入口

1. 在模拟求解选择一个单工点，记录当前各池 `quantity`。
2. 用同一 Scenario 和数量构造 AI 单方案。
3. 分别求解。

预期：两者都是一次调用，资源快照相同，最大延期/总工期目标一致，无新增资源。

### 样例 B：当前资源冗余

1. 将某个非必要池当前 `quantity` 设置为大于 0，`max_quantity` 保持不小于当前数量。
2. 运行固定工期求资源。

预期：全局搜索下限仍为 0，可推荐该池为 0；结果页面明确区分候选与详细验证。

### 样例 C：候选详细排程未满足

1. 使用定向 fixture 使全局容量模型返回候选，但详细 solver 返回 `OPTIMAL` 且延期。
2. 运行固定工期求资源。

预期：候选保留，详细状态 `not_met`，`candidate_verified=false`，没有任何增配、重搜或第二次详细调用。

### 样例 D：限时未确认

1. 使全局搜索返回 `UNKNOWN`。
2. 再使候选存在但详细排程返回 `FEASIBLE` 且延期。

预期：前者直接 `unconfirmed` 且不跑详细排程；后者保留排程并标记 `unconfirmed`，不重试。

## 8. 最终组合门禁

相关定向测试通过后只运行一次完整门禁：

```powershell
npm.cmd run verify
```

若完整门禁失败，按失败证据区分：

- 056 引入的失败：在本工作项内修复并重跑最小失败集；
- 工作树中已有的无关失败：记录具体命令、文件和错误，不修改无关功能，也不重复运行完整门禁。

## 验收记录模板

```text
固定资源模拟 solver 调用：1
固定资源 AI solver 调用：1
全局最少资源搜索调用：0/1
详细固定资源调用：0/1
自动增配/二分/压力/最佳努力调用：0
默认资源下限：0
目标顺序：max_target_delay_days -> makespan_days
详细业务状态：met/not_met/unconfirmed/infeasible
候选已验证：true/false
范围：ALL/WORKPOINT
定向测试：PASS/FAIL
typecheck/build：PASS/FAIL
完整门禁：PASS/FAIL/既有无关失败
```

## 2026-07-22 实施验收记录

- OpenAPI YAML：`contract ok`。
- US1 固定资源/目标/路由相关用例通过；包含 AI 助手全文件的组合命令为 `34 passed, 39 failed`，39 项与实施前基线一致，均属于并行 059 工点资源改造后的旧测试（缺少必填 `target_workpoint_id` 或仍构造旧资源池结构）。
- US2 application、单工点、目标和路由组合：`18 passed`。
- API、范围与契约组合：`28 passed`；新增统一结果路由/旧响应兼容用例另有 `2 passed`。
- 前端 056 契约与展示：相关用例通过；组合文件为 `27 passed, 1 failed`，唯一失败是并行架梁 v2 镜像契约缺失，与 056 无关；另一个宽泛正则运行中的资源页面 CDP 用例因环境超时失败，与 056 无关。
- `npm.cmd run typecheck`：通过。
- `npm.cmd run build`：通过，仅保留既有 chunk 大小告警。
- `npm.cmd run verify`：仅运行一次；类型检查通过，全量后端测试在约 72% 时已出现既有/并行失败，并于 120 秒超时退出。超时遗留的本次 pytest 进程已终止；未重复运行完整门禁。
