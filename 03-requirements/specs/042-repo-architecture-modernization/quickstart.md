# 快速验证：项目架构治理与模块化升级

本指南用于验证每个迁移批次保持行为、接口、构建和文档兼容。命令在仓库根目录执行。

## 1. 当前基线（2026-07-16）

```text
后端：328 passed, 1 skipped
前端 Node：21 passed
前端构建：通过，1628 modules transformed
构建产物：JS 470.62 kB（gzip 136.32 kB），CSS 86.82 kB（gzip 16.59 kB）
```

环境：Python 3.12.13、Node.js 24.14.1、npm 11.11.0、TypeScript 5.9.3。

Batch 0 采集结果：45 个 `/api` 路由、153 个 Pydantic 模型、40 个前端 API 函数；固定夹具位于 `backend/tests/fixtures/architecture/` 和 `frontend/tests/fixtures/architecture/`。三份 npm 锁文件与 `requirements.txt` 未发生变化。

Batch 0 门禁结果：后端新增架构专项 `10 passed`，前端兼容专项 `3 passed`，`npm.cmd run verify:architecture` 全部通过。历史已跟踪的 Office 临时锁文件和 `.netlify-cli-runtime` 已登记为 Batch 7 待确认资产，不在本批删除或取消跟踪。

Batch 1 文档结果：维护者定位 12/12 通过；`backend/tests/test_documented_project_facts.py` 4 passed；`validate_docs.py` 对 9 个入口/架构文档检查通过；当前入口中旧 `netlify/functions/api.mts` 引用已清零并改为未部署的 `netlify/demo-functions/api.mts`。`041` 仍保持 74/95。

Batch 2 HTTP 结果：`main.py` 从 577 行收敛为 app/endpoint 兼容 façade，实际装配迁入 `bootstrap.py`，路由按 system/scheduling/assistants/project_girder/plan_control 分组。新增 ASGI 协议级 HTTP/路由测试 12 passed；既有计划管控、架梁 API、桥梁导入与 OpenAPI 专项 29 passed；冻结的 45 操作 manifest 完全一致。因环境未安装 `httpx`，测试使用无新增依赖的 ASGI 客户端；静态资源、直接文件和 SPA 回退均已覆盖。

Batch 3A 契约结果：153 个 Pydantic 定义迁入 `app/contracts/_models.py`，六个领域模块提供受控发现入口，`app.models` 收敛为 7 行兼容 façade，37 个内部消费者改用 `app.contracts`。新增领域契约与旧导入专项 9 passed，完整 schema/公开导出/固定场景基线零差异。集中 `_models.py` 暂时保留定义顺序以避免前向引用和循环依赖，领域模块是新代码的公开所有权入口。

Batch 3B 业务边界结果：新增 importing、assistants/parameter、assistants/resource、girder_planning application、plan_control 和 config 入口；router/bootstrap 已切换到新边界。旧 services/local 模块仍作为兼容实现源，未复制实现或改变存储路径。新旧 façade 对象身份与配置路径测试 4 passed，OpenAPI 专项保持通过。

Batch 4 场景/求解器结果：场景实现迁入 `scheduling/application/_scenario.py`，求解实现迁入 `scheduling/solver/engine.py`；generation/application/results/milestones/diagnostics/constraints/objectives/strategies 提供领域入口。`app.scenario` 和 `app.solver` 通过模块别名保持私有导入及 monkeypatch 兼容。新增分域测试 13 passed，原 `test_scheduler.py` 174 passed，公开导入、schema、OpenAPI 和固定场景哈希零差异；seed/worker/时限/warm-start/阶段路由因使用同一 engine 实现未改变。

Batch 5A 前端端口结果：202 个共享导出迁入 `contracts/scheduler.ts` 并按域提供入口，40 个 API 函数迁入 `_schedulerApi.ts` 并按六个域重导出；40 个内部类型消费者和四个 feature API 消费者已切换。兼容 Node 专项 7 passed，TypeScript/Vite 构建通过；主 JS/CSS 仍为 470.62/86.82 kB（gzip 136.32/16.59 kB），与基线一致。

Batch 5B 工作台结果：`app/App.tsx` 收敛为 6 行稳定装配入口，原工作台迁到 `Workspace.tsx`；场景加载/任务生成/求解 workflow、场景指纹失效和 busy/error 协调迁入 `app/workflows/` 与 `useWorkspaceController.ts`。任务视图、结果 presenter、计划管控 presenter 和 feature 公开入口已建立，跨 feature 消费改走 `index.ts`。新增 Node 专项后共 35 passed，TypeScript/Vite 构建通过；主 JS 为 471.51 kB（gzip 136.80 kB），相对 470.62 kB 基线增加 0.19%，低于 5% 门禁。

Batch 5C 样式与视觉结果：原 `styles.css` 4,927 行按原顺序拆入 tokens/base/layout、公共组件和五个 feature 样式，聚合入口为 12 行；重组逐行比较完全一致，构建 CSS 仍为 86.82 kB（gzip 16.59 kB）。使用只读 `HEAD` 基线、同一数据快照和 Playwright 1440×900 视口对任务、结果、架梁、计划管控、AI 多方案五页截图，五组 SHA-256 均完全一致，控制台 0 error/0 warning；详见 `visual-regression.md`。回退只需按聚合顺序恢复单文件。

US2 全量门禁：后端 `370 passed, 1 skipped`，前端 `35 passed`，`tsc && vite build` 通过；后端/前端冻结契约、依赖方向、仓库卫生和 9 份文档事实门禁全部通过。热点入口规模为 `App.tsx` 6 行、`styles.css` 12 行、`types/scheduler.ts` 2 行、`schedulerApi.ts` 2 行、`backend/app/main.py` 119 行；兼容 façade 未新增依赖或数据迁移。

Batch 6 运行部署结果：新增单服务冒烟、Docker/Netlify 契约、5% 构建预算和 800 任务/300 分跨 10% 性能门禁。`smoke_single_service.ps1` 实测健康、根页面、静态资源和 SPA 回退均为 200；完整性能专项 2 passed/64.42 秒，相比 65.32 秒冻结基线未退化。Vite `/api` 代理、`VITE_API_BASE_URL`、Netlify `frontend/dist`/Node 22/SPA 回退和无 Functions 目录均由 2 个 Node 契约用例保护。当前机器没有 Docker CLI，已执行 Dockerfile 运行契约与根/`examples/` 双路径样例测试 3 passed，未声称完成本机镜像构建。统一 `npm.cmd run verify` 实测通过：后端 374 passed/2 skipped、前端 37 passed、构建、包体和架构门禁全部通过。

## 2. 实施前检查

```powershell
git status --short --branch
.\.venv\Scripts\python.exe --version
node --version
npm.cmd --version
```

预期：只存在本功能已确认的改动，不覆盖用户无关改动；版本与项目依赖兼容。

在 Batch 0 中生成并纳入测试夹具：

- OpenAPI `method + path + schema` manifest。
- 代表性 Pydantic JSON Schema 与 JSON dump 快照。
- `app.models`、`app.scenario`、`app.solver` 兼容导入清单。
- `types/scheduler.ts`、`schedulerApi.ts` 兼容导出清单。
- `requirements.txt`、根/前端/辅助工具 `package.json` 与锁文件的运行时依赖清单。
- 固定排程、架梁、计划管控和前端失效行为基线。
- 仓库资产清单、正式二进制哈希和 `041` 未完成任务清单。
- 每个 Batch 的前置条件、验证证据、回退步骤、阻断状态和审批证据模板。

## 3. 每批自动门禁

### 后端全量测试

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

预期：不低于基线通过数量；跳过项只能保持或减少，不得新增未解释失败。

### 前端 Node 测试

```powershell
npm.cmd --workspace frontend test
```

预期：全部用例通过，重点保护场景指纹、旧结果失效、进度日期和新增的 API/类型兼容门禁。

### 类型检查与生产构建

```powershell
npm.cmd run build
```

预期：`tsc && vite build` 通过；纯重构后的主 JS/CSS 体积不比基线增长超过 5%。

### 变更卫生

```powershell
git diff --check
git status --short
```

预期：无空白错误；无密钥、日志、缓存、依赖目录、构建产物或 Excel 临时锁文件被误纳入。

### 运行时依赖基线

比较 `requirements.txt`、根/前端/辅助工具 `package.json` 和锁文件依赖树。预期：纯重构不新增包、不升级版本、不改变锁文件依赖树；任何差异都必须先停止并取得独立确认。

## 4. 后端兼容专项

Batch 2～4 必须执行：

1. 比较重构前后 OpenAPI route manifest，无未经批准差异。
2. 运行真实 HTTP 测试，覆盖健康检查、核心场景、错误状态码、静态资源和 SPA 回退。
3. 验证旧 Python import 仍能导入并指向唯一实现。
4. 比较代表性模型的 JSON Schema 与 `model_dump(mode="json")`。
5. 使用固定输入比较：
   - 任务 ID、开始/结束日期；
   - 资源分配；
   - 里程碑结果；
   - 目标分解；
   - 诊断码和来源标签；
   - 方案二输出状态和候选排序。
6. 验证 `.local-data` v1/v2 示例的加载、写回、版本冲突和幂等复用。
7. 运行 800 个综合任务、300 个架梁分跨性能夹具；不得超过既有 10 分钟门禁，同环境典型运行不应恶化超过 10%。

## 5. 前端兼容专项

Batch 5 必须执行：

1. 旧 `frontend/src/App.tsx` 默认导出仍可编译。
2. 旧 `types/scheduler.ts` 导出名称和 `schedulerApi.ts` 40 个函数名保持。
3. 验证 `domain` 无 React/网络依赖、feature 不导入其他 feature 内部文件、无新增循环依赖。
4. 场景修改后 generated、solve、comparison、integrated snapshot 全部失效。
5. 完成以下浏览器冒烟旅程：
   - 加载默认场景并生成任务；
   - 固定资源、最少资源、资源成本三类求解；
   - 保存结果并比较方案；
   - AI 参数建议解析、审阅和应用；
   - AI 资源方案生成、求解、比较和推荐；
   - 架梁专项导入、配置、校验和综合排程；
   - 计划基线、进度快照、预测和调整闭环。
6. CSS 迁移前后对任务视图、结果视图、计划管控、架梁专项和弹层进行相同视口截图对比，核对布局、级联、定位和响应式行为。

## 6. 单服务健康检查

先构建前端：

```powershell
npm.cmd run build
```

启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

另一个 PowerShell 窗口执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

预期：健康检查成功，`http://127.0.0.1:8000/` 返回前端页面，静态资源和 SPA 回退正常。

## 7. 仓库与文档门禁

- 在执行资产迁移前展示逐文件旧路径、新路径、类别、跟踪策略、引用、哈希和回退方式，并记录用户二次明确确认；未确认项不得移动或取消跟踪。
- 根目录只包含 [repository-layout-contract.md](./contracts/repository-layout-contract.md) 允许的入口和兼容文件。
- `README.md`、`agent.md`、`docs/README.md`、`docs/architecture/` 内部链接 100% 有效。
- 入口文档列出的 API、脚本、环境变量、模块和部署路径能由当前代码/配置验证。
- `specs/README.md` 能解释所有现有规格目录；不移动或重编号历史规格。
- `deliverables/` 的正式资产有清单和哈希；`artifacts/` 的中间件默认忽略。
- `041` 原有已完成/未完成任务状态与迁移前清单一致。
- `tools/ai-ppt-system/` 的本地类型/布局验证通过；`tools/demo-api-mirror/` 的无部署语法/类型检查通过；`tools/delivery-builders/` 使用固定夹具完成一次构建和复核。

## 8. 规模目标

最终检查：

- 后端 `main.py` 只保留 app 兼容入口和必要转发。
- 后端 `models.py`、`scenario.py`、`solver.py` 只保留受测试保护的兼容 façade，不再承载新业务实现。
- 前端 `app/App.tsx` 与全局 `styles.css` 行数至少较基线下降 70%。
- `types/scheduler.ts` 和 `schedulerApi.ts` 收敛为短兼容出口。
- 新业务模块不需要修改无关的全局热点文件。

## 9. Batch 7 资产迁移验收结果

- 审批：用户已明确确认更新后的 140 项逐文件清单。
- 迁移后验：140/140 源路径消失、目标路径存在、迁移目标哈希一致；90 个保持跟踪、34 个取消跟踪、16 个本地日志仅移动。
- 根目录日志：16 → 0；历史日志位于 `.local-data/logs/legacy/` 且被忽略。
- 当前文档：入口、架构、产品、工程、验证和调研路径已更新；历史 specs 的旧路径由 `docs/archive/path-migration.md` 解释。
- 工具：PPT `typecheck + layout` 通过且 0 finding；参考 API `noEmit`/未部署检查通过；泸古验证工作簿 8 个工作表全部渲染，临时构建与正式交付物独立导入成功，公式错误扫描为 0。
- 专项门禁：治理、Docker 样例、文档事实和桥梁导入 30 passed；文档链接/API 事实检查通过。
- 本地例外：未获批清单不包含旧工具依赖缓存、旧验证脚本依赖 junction 和未跟踪的 `泸古1标架梁工点导入模板.xlsx`，均未移动或删除。

## 10. 完成证据

每个 Batch 在 `tasks.md` 对应任务下记录：

- 修改文件与迁移路径；
- 自动验证命令和结果；
- 契约/行为快照差异；
- 性能与包体差异；
- 人工旅程和视觉检查结果；
- 未覆盖风险与回退方式。

所有批次完成后再运行 `$speckit-converge`，检查代码、规格、计划、任务和文档是否一致。
