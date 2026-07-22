# 快速验证：单工点模拟求解

## 前置条件

- 使用包含至少两个桥梁工点的已确认项目主数据版本。
- 为待测工点配置至少一组能覆盖其任务需求的合法工点独享或项目共享资源。
- Windows 命令从仓库根目录执行，使用现有 `.venv` 和已安装 Node 依赖。

## A. 后端范围与兼容契约

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_scheduling_routes.py 04-demo/backend/tests/scheduling/test_single_workpoint_solve.py -q
```

期望：

- 不传 `workpoint_id` 的四个端点保持全项目行为，`solve_scope.mode=ALL`。
- 传有效桥梁工点 ID 时，任务全部属于该工点，关系无悬空，里程碑均能命中，资源仅来自合法池。
- 不存在、过期或非桥梁工点 ID 返回 422，且不回退全项目。
- 三类求解和所有备选结果保持相同 `solve_scope`。
- 单工点或混合范围方案比较被后端拒绝。

## B. 资源、里程碑和 solver 回归

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py 04-demo/backend/tests/scheduling/test_solver_constraints.py 04-demo/backend/tests/scheduling/test_fixed_resource_application.py 04-demo/backend/tests/scheduling/test_resource_search_application.py 04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py -q
```

期望：

- 同类型多池仍按稳定池 ID 独立。
- 项目共享和工点独享候选边界、互斥行为和零转场语义不变。
- 数量为 0、停用、缺失或作用域不匹配继续返回 `RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE`。
- 里程碑匹配函数抽取前后代表性硬/软里程碑结果一致。

## C. 前端范围状态和结果保护

```powershell
npm.cmd --workspace 04-demo/frontend test
npm.cmd run typecheck
npm.cmd run build
```

期望：

- 下拉包含“全部工点”和当前桥梁工点；加载、空态、失败态、忙碌态可观察。
- 三个求解按钮发送相同 `workpoint_id`。
- 范围切换改变指纹并失效生成、结果、固定工期基准和比较状态。
- 单工点结果显示名称与 ID，保存按钮被阻止且显示原因。
- 全项目结果保存和比较仍可用。

## D. Netlify 镜像契约

镜像相关自动化测试应覆盖同一查询字段、422 错误和 `solve_scope` 响应。随后执行：

```powershell
npm.cmd run verify:architecture
```

期望：FastAPI、前端共享类型、Netlify 镜像和架构基线不存在字段或端点差异。

## E. 参考项目性能验证

使用当前确认项目的最大工点 `WP-BR-YNH`：

1. 先生成全项目输入，记录任务数和关系数。
2. 选择 `WP-BR-YNH`，设置 3 秒求解上限并运行固定资源最短工期。
3. 记录单工点任务数、关系数、求解状态、solver wall time 和端到端耗时。

期望：

- 全项目参考值约为 1,586 个任务、1,872 条关系。
- 单工点参考值约为 225 个任务、266 条工点内关系，任务量下降至少 80%。
- 合法资源条件下，端到端 8 秒内返回 `FEASIBLE` 或 `OPTIMAL`，结果任务数等于生成任务数。
- 若当前资源数量为 0 或没有合法候选，应返回资源阻断诊断；该结果不计为性能失败，也不得通过临时补充默认资源规避。

## F. 停止条件

上述定向验证与架构门禁通过后停止；不因本功能额外运行发布、生命周期清理或全仓验证，除非实施阶段发现共享契约或架构基线的非局部回归。

## G. 实施证据（2026-07-20）

参考项目主数据版本：`pmv-598b95a015ab404280cf8e87097caa0a`。按生成任务数动态确认最大桥梁工点仍为 `WP-BR-YNH`（永宁河特大桥）。性能验证仅在内存中为其 6 类实际资源需求各配置 1 个合法资源，不写入默认资源或项目数据。

| 指标 | 实测值 |
|---|---:|
| 全项目任务 / 关系 | 1,586 / 1,872 |
| 单工点任务 / 关系 | 225 / 266 |
| 任务量下降 | 85.81% |
| 求解状态 / 返回任务 | `OPTIMAL` / 225 |
| solver wall time | 3.135 秒 |
| 端到端耗时 | 3.157 秒 |

验证记录：

- 单工点后端契约、三类求解、非法 ID、零资源诊断及路由定向测试通过。
- 前端范围指纹、API/镜像兼容、结果展示和保存保护定向测试通过；TypeScript 类型检查和生产构建通过。
- 资源回归组 27 项通过；4 项因当前默认场景资源池为空、旧用例仍查找 `cap_team` 而失败，本功能未修改默认资源配置。
- 前端全套测试的大部分用例通过；既有 `resourceAssistantPoolIdentity` 数据 URL 相对导入失败，`resourceWorkpointRuntime` 因 Chrome DevTools `Page.enable` 60 秒超时失败，均未进入本功能代码断言。
- 架构基线只接受 `SolveScope`、可选查询字段、相关导出/依赖和最终构建体积；当前默认场景资源快照漂移不并入本功能基线。
- 最终 `git diff --check` 通过；`verify:architecture` 停在后端基线比对，因为本地默认场景已从基线的 9 个资源池漂移为 0，且既有 `resource_pools` schema 快照仍保留 `minItems: 1`。为遵守“不接受无关架构漂移”，T027 保持未完成。
