# 实施计划：路面求解时限手动输入

**功能目录**：`075-pavement-solve-time-input` | **日期**：2026-09-28 | **规格**：[spec.md](./spec.md)

## 概要

增加一个默认 15 秒的页面级输入框。普通求解在请求快照中使用输入值；窝工请求增加可选的独立运行预算，使本轮计算能调整时限，同时保留已有完整指纹和基准校验。复用既有有限预算、流式结果和进度显示，不改求解策略。

## 技术上下文

- 语言/依赖：现有 Python/FastAPI/Pydantic/OR-Tools 与 TypeScript/React/Vite，不升级依赖。
- 存储：仅页面状态和本次请求，无新增持久化。
- 测试：pytest、Node 内置测试、前端构建、临时浏览器页验证。
- 目标平台：Windows 本地服务与路面页面。
- 性能：沿用现有建模与搜索的统一截止时间，不增加额外搜索阶段；通信仍保留现有 30 秒收尾余量。
- 约束：基准工期上限、完整输入指纹、任务合法性、多线程及 LNS 保持。
- 范围：路面工具栏、请求构造、窝工运行预算透传、相关共享契约和测试。

## 生命周期归属

引用 [规格的生命周期归属](./spec.md#生命周期归属)。本功能源码及测试沿用以下 04-demo 路径；不创建额外业务模块。

## Constitution 检查

- 需求来源、代码事实、可观察验收、错误和兼容行为已明确，小范围需求无需独立评审。
- 求解目标/约束保持；只改变运行预算的交互与传递，单位和默认值已明确。
- 可选请求字段同步后端、前端类型、API 客户端及契约快照；旧调用方不提供字段仍有效。
- 主数据、配置、原浏览器结果不主动写入或刷新；无迁移和清理任务。
- 设计前与设计后均通过；无宪章违反项，无待澄清事项。

## 项目结构与设计

### 本功能文档

`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/solve-budget.md`、`quickstart.md`、`tasks.md`。

### 1. 页面与请求控制

- `04-demo/frontend/src/app/Workspace.tsx`：PavementWorkspace 新增字符串形式的预算草稿，初值为 15；字段旁显示校验错误；忙碌时禁用输入；两个按钮共享校验结果。
- 草稿不写入 scenario，也不进入业务 fingerprint 或 dirty。修改草稿不会取消结果或使窝工入口失效。
- `04-demo/frontend/src/app/workflows/solveWorkflow.ts`：现有 request 增加可选本轮预算参数，未传保持原行为；普通求解使用复制后的 scenario.time_limit_seconds；窝工用当前业务 scenario，加上基准 generated.schedule_input.time_limit_seconds 还原计算来源的原时限，再独立传入本轮预算。
- 只恢复基准原时限，不能从基准覆盖当前任务/资源等业务参数；服务端仍逐字段比对完整输入。不得原地改 scenario、baseline 或 generated。
- `04-demo/frontend/src/api/_schedulerApi.ts`：窝工请求携带可选 time_budget_seconds；等待时间按有效预算加 30 秒计算。既有普通请求按本次 scenario.time_limit_seconds 计算。

### 2. 窝工预算与基准分离

- `04-demo/backend/app/contracts/_models.py` 的 PavementIdleOptimizeRequest 增加 time_budget_seconds，可缺省或 null；提供时要求有限且 >0。
- `04-demo/frontend/src/contracts/scheduler.ts` 同步可选字段类型。
- `04-demo/backend/app/api/routers/scheduling.py` 取独立预算优先、scenario.time_limit_seconds 回退，启动事件与内部调用共用该有效值。
- `04-demo/backend/app/scheduling/application/pavement.py` 仅传递新预算，不改 prepare_pavement_idle。
- `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 的 solve_pavement_idle 增加可选运行预算；仅用于 deadline 和本轮 time_budget_seconds 元数据。基准工期、校验输入、结果任务定义、输入指纹和第一阶段耗时都保留。
- 普通求解无需后端修改。旧请求、直接内部调用省略新参数时沿用原预算。
- 演示镜像继续明确拒绝路面求解，不新增伪造支持。契约验证覆盖该行为。

### 3. 验证与共享快照

- 后端：`04-demo/backend/tests/test_pavement_contracts.py`、`test_pavement_api.py`、`test_pavement_stream.py`、`test_pavement_hybrid.py`。
- 前端：`04-demo/frontend/tests/pavementLiveSolve.test.mjs` 扩展预算传递、原对象保护、入口与旧调用方回退断言；复用已有断线/异常保留结果测试。
- `04-demo/backend/tests/fixtures/architecture/backend-baseline.json` 和 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`：用现有 capture 脚本更新必要契约差异并核对；不混入无关 API 变更。
- 构建后在新临时页检查输入、按钮和本轮预算。原用户页面不刷新；真实求解可提前最优，预算数值验证不强制耗满 30 秒。
- 本仓库未提供 update-agent-context 脚本，已检查 .specify；不新增第二份 agent 事实文件或工作流脚本。

## 依赖与验证顺序

先同步预算契约与后端透传，再接前端请求和输入框，最后运行一次相关测试、构建与临时页验收。全部范围只服务本次输入需求，不实施此前讨论的两阶段窝工策略。

## 复杂度跟踪

无需例外。选择一个可选运行字段，避免重写既有指纹算法和历史方案兼容规则。
