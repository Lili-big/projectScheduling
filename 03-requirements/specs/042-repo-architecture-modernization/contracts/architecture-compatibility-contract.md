# 架构重构兼容契约

本契约定义 `042` 实施期间和完成后必须保持的外部行为。任何不满足项都属于阻断回归，而不是“内部重构差异”。

## 1. HTTP API

- 保持当前全部 45 个 `/api` 路由的方法、路径和路由参数。
- 保持成功状态码、业务错误状态码、错误 `detail`、响应模型和字段语义。
- 保持兼容接口：`GET /api/demo`、`POST /api/generate-wbs`、`POST /api/solve`。
- 保持核心主链：

```text
GET /api/demo-scenario
  -> POST /api/generate-schedule-input
  -> POST /api/solve-scenario | /api/solve-min-resources | /api/solve-resource-cost
  -> POST /api/compare-scenarios
```

- 保持 AI 参数助手、AI 资源助手、架梁专项、综合排程和计划管控现有路由组。
- 实施前生成按 `method + path + request schema + response schema + documented statuses` 比较的 route manifest；拆分 router 后必须无未经批准差异。

## 2. 后端 Python 入口

- `uvicorn app.main:app --app-dir backend` 继续有效。
- `app.main:app` 继续导出 FastAPI 实例；现有直接调用的 endpoint 名称在实施期保持可导入转发。
- `app.models` 完整重导出现有契约名称。
- `app.scenario` 保持现有公开场景函数；现有测试使用的私有入口在对应测试迁移前保留转发。
- `app.solver` 保持现有公开求解函数、必要常量和实施期兼容转发。
- `app.main` 的 `/assets` 挂载和 SPA catch-all 行为保持不变。

## 3. 共享数据与结果语义

- 保持 `ScenarioInput -> GeneratedScheduleInput / ScheduleInput -> ScheduleResult / ScenarioSolveResult` 字段、snake_case JSON 和默认值语义。
- 保持 `schedule_source`、`performance_path`、`stats`、`objective_breakdown`、诊断码、里程碑状态、方案二输出状态和候选排序语义。
- 保持 CP-SAT 随机种子、worker、时间预算、warm start、阶段路由、回退条件和资源搜索顺序。
- 重构等价比较忽略 wall time、日志顺序等非业务元数据，但必须比较任务日期、资源分配、里程碑、目标分解、诊断和来源标签。

## 4. 配置、存储与稳定标识

- 保持 `.local.env` 和现有环境变量名称。
- 保持“代码默认值 → `backend/app/default_scenario_config.json` → `.local-data/scheduler-config.json`”合并顺序。
- 保持 `.local-data/project-structure-params.json`、`.local-data/plan-control-store.json` 的路径、schema、版本冲突和写回行为。
- 保持 `stable_id`、`stable_fingerprint`、场景指纹、幂等复用和旧结果失效语义。
- 根样例 Excel 只有在新路径兼容读取、Docker 复制、文档和回归测试全部就绪后才能迁移；迁移期保留旧路径回退。

## 5. 前端入口与行为

- `frontend/src/main.tsx` 和 `frontend/src/App.tsx` 默认导出入口保持有效。
- `frontend/src/types/scheduler.ts` 继续导出现有名称。
- `frontend/src/api/schedulerApi.ts` 继续导出现有 40 个公开函数名和参数/返回类型。
- 保持 `VITE_API_BASE_URL`、90 秒请求超时、生产环境 API 基址保护和 Vite `/api` 代理。
- 保持场景指纹变化后 generated、solve、comparison、integrated snapshot 的失效行为。
- 保持关键页签、三类求解、保存对比、AI 参数确认、资源助手、计划管控和架梁专项主要用户流程。
- CSS 拆分期间保持现有选择器语义、导入顺序、弹层定位和响应式行为。

## 6. 命令与部署

以下命令继续有效：

```powershell
npm.cmd install --cache .npm-cache
npm.cmd run build
npm.cmd run frontend:dev
npm.cmd run frontend:preview
.\.venv\Scripts\python.exe -m pytest backend\tests -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

- `Dockerfile` 继续启动 `app.main:app`，并可读取默认示例数据。
- `netlify.toml` 继续构建 `frontend/dist` 并发布静态前端。
- Netlify 参考 API 的目录可以迁移到 `tools/`，但不得被描述为正式 FastAPI 后端。

## 7. 规格与文档状态

- `specs/041-girder-scheduling-integration/tasks.md` 的完成/未完成状态不因重构自动变化。
- `README.md`、`agent.md`、`docs/README.md` 和架构文档必须区分当前实现、规格目标、历史资料和待确认项。
- 历史规格路径保持稳定；失效引用通过分类清单处理，不通过批量伪造目标文件消除。

## 8. 兼容层生命周期

- 本功能只创建和维护兼容 façade，不删除旧入口。
- 旧入口删除必须在未来独立规格中列出消费者、迁移窗口、弃用通知和破坏性版本策略，并重新获得用户确认。
