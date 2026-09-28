# 实施计划：路面任务自动准备与统一工序链

**目录**：`066-pavement-task-preview` | **日期**：2026-09-24 | **分支**：`codex/road-pavement-engineering`  
**输入**：[spec.md](./spec.md)。状态：用户已确认tasks，实施与验收已完成。

## 概要与技术上下文

复用已有POST /api/generate-schedule-input作为计算来源；前端增加自动请求状态与按施工段组织的统一清单。工艺逻辑页统一维护关系和间歇，后端同步排除末尾养生/验收。不新增API、持久任务表或独立工期计算器。

现有TypeScript/React19/Vite6、Python/FastAPI/Pydantic、node:test/pytest；不增加依赖。目标平台为本地8000已构建页面。性能边界：当前25段100层，合并快速修改请求（建议250ms防抖），只对当前输入请求一次，不调用CP-SAT；不承诺未经验证的延迟指标。

持久化仍用现有项目主数据和配置文件。预览内存缓存随项目/版本/输入变化失效；工效选择只在点击保存时落盘。资源、路床日期和层间条件缺失不掩盖已生成结果，也不放松其求解校验；末层条件明确移出本轮范围。

## 生命周期及实施范围

沿用[规格归属](./spec.md#生命周期归属)。源码及测试：
- `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx`：路面统一分组表、工效选择、关系、缺项、保存/重试入口。
- `04-demo/frontend/src/features/taskView/styles.css`：紧凑分组、列宽与单位不换行，保留桥梁样式作用域。
- `04-demo/frontend/src/domain/pavement.ts`：纯展示投影；复用层与依赖行解析，不创建另一套排程规则。
- `04-demo/frontend/src/app/workflows/scenarioWorkflow.ts`：可注入生成函数的请求状态控制，序号/指纹防旧响应覆盖，可测异步行为。
- `04-demo/frontend/src/app/Workspace.tsx`：路面页签触发、内存配置变化联动、保存及现有求解状态隔离。
- `04-demo/frontend/tests/pavementTaskPreview.test.mjs`：新增投影、异步次序/失败/缓存测试。
- `04-demo/frontend/tests/pavementWorkflow.test.mjs`：复用既有工效/关系/指纹回归。
- `04-demo/frontend/src/features/logic/LogicTab.tsx`、`04-demo/frontend/src/styles/domain-editors.css`：统一工序链，移除重复养生表；保留分段覆盖、非末层验收日期及配套/跨段配置。
- `04-demo/backend/app/scheduling/generation/pavement.py`：层间关系唯一生效、末尾条件不参与生成、缺项诊断只针对有效前置关系。
- `04-demo/backend/app/scheduling/solver/strategies/pavement.py`：允许无末层交付条件，旧直接输入诊断、以施工完成为目标和完成日期；层间、资源等约束保留。
- `04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/tests/pavementResults.test.mjs`：以施工完成显示本轮结果，不显示末层交付节点；旧结果识别为需重算。
- `04-demo/backend/tests/test_pavement_generation.py`、`04-demo/backend/tests/test_pavement_api.py`：生成能力、旧条件兼容、缺项仍返回已知结果及直接求解门禁样例。
- `04-demo/frontend/tests/contractsCompatibility.test.mjs`、`04-demo/backend/tests/test_pavement_solver.py`：相关兼容和生成/求解同输入一致性回归。
- 本目录quickstart/tasks及规格索引记录完成证据。

## Constitution检查

研究前：来源、业务三点、现有权威算法及原页面缺口明确；无需阻塞澄清。
设计后：输入、计算、结果状态、兼容、并发和测试均有明确合同；除用户明确要求的末尾条件/完成口径外，不改业务硬约束；不复制持久任务；资产归属合法；不新增依赖。无违反项。实施前仍需要确认tasks。

## 实施决策

- **D1**：进入任务页或当前场景变化后请求现有生成API，范围固定为当前项目全部工点；独立于模拟求解scope。保留已完成同指纹结果供返回页签复用。
- **D2**：用独立preview状态，避免自动预览覆盖solved/generated历史求解状态。防抖在页面层，控制器管理请求序号和指纹；输入改变即旧表不再标为当前，离页取消提交资格，失败显式重试。
- **D3**：以当前启用层构建身份/分组骨架，按component_id对齐后端construction任务；正天数配套按ancillary step ID加入相应工序前，0天步骤无施工行。不按任务返回顺序直接排表。
- **D4**：显示工期、计量工程量、工效及实际工艺/方案取自后端任务字段。工效下拉按process_id定位库；未生成任务保留当前选择及缺项，不用无效选择自动回退有效方案。单任务工期列为“天”，单套含义放工效说明，不写“天/套”。
- **D5**：层间已知关系基于后端precedence_links，并结合已有pavementDependencyRows的规则来源/未确认状态；必要时给该展示函数增补源/目标ID，不更改其匹配规则。缺失间歇显示N待确认；缺少任务不得沿用生成器跳过缺项层形成的捷径边。固定跨段关系按设置核对源目标，保留完整名称；循环/失效引用展示诊断而非自动修复。
- **D6**：一张分组表替换两张表，列为工序、计量工程量、工效方案、工效、工期、前置工序、逻辑关系。分组默认展开；第一道施工任务的路床条件为独立说明，不伪造前置任务。移除“到模拟求解生成”引导及模拟页手动生成按钮；保留求解、保存参数及既有结果。
- **D7**：路床、层间关系和资源缺项按层或段标注并汇总可展开详情；有效已算工期仍显示。末层养生不作为缺项。量/工效错误的行工期为待完善。技术间歇不累加到施工工期。共享机组不被改成专用，任务表不再显示旧“专用机组”文案。
- **D8**：自动计算只使用当前内存输入，不保存；本页增加保存工效选择入口，调用既有save及dirty/error状态，失败保留编辑。修改工效、主数据/关系后任务自动刷新，历史求解结果按既有指纹过期。
- **D9**：保留桥梁工作区及API/演示镜像现有行为。仅修复本需求验收要求的缺陷，不顺带实现064路床三态或末层可用节点。旧结果若包含readiness节点或旧目标earliest_deliverable_readiness，保留为历史并提示重新求解，不冒充本轮结果。
- **D10**：沿用现有关系行及统一/分段选择器作为唯一工序链；移除整块施工段养生表、批量等待和“末层在下方维护”提示。层间配套和固定跨段顺序留在默认收起的“其他配置”；已有非末层验收日期移入相应分段关系行的可选条件，沿用原layer_conditions存储，编辑日期时不改旧wait_days/basis_note，不新增日期必填。末层不展示日期输入。
- **D11**：关系优先级保持分段>统一>历史条件；历史非末层等待以FS+N显示，用户编辑后写dependency_rules，旧layer_conditions不自动删除/迁移。显式N替代对应层间等待，不叠加；显式N为空仍为待确认，不能回退旧值假装已确认。既有非末层验收日期、零天配套和跨段限制继续生效并可见，非FS关系不被强加FS养生。
- **D12**：生成器按当前启用层序确定每段末层，不读取其养生/验收条件，不生成readiness_conditions，不要求末层wait_basis。求解器对新输入不要求末层条件；对携带旧readiness_conditions或非零末层wait/accepted边界的直接输入报可操作的重新生成错误，不静默抹掉请求数据。模型最小化max(task.end)，末层不生成等待区间；有显式跨段后继时仍执行该边。新结果目标标识earliest_construction_finish，plan_finish_date使用construction_finish_date（start_date+max(end)-1）；既有ready_offset/date只保留为完成边界兼容字段，不作业务可交付展示。末层完成里程碑按实际finish_date校核，非末层验收约束不变。

## 阶段产物与验证

[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/task-preview.md](./contracts/task-preview.md)、[quickstart.md](./quickstart.md)、[tasks.md](./tasks.md)。现有脚本目录没有update-agent-context.ps1，故记录缺失，不添加替代脚本或改AGENTS。

唯一验证批次见quickstart；页面核对用现有当前项目，不改客户数据以伪造可求解状态。不存在额外复杂度或架构例外。

