# 实施计划：AI 多方案按工点推进资源

**分支/目录**：`053-ai-workpoint-resource-comparison` | **日期**：2026-07-20 | **规格**：[spec.md](./spec.md)

**输入**：来自 `03-requirements/specs/053-ai-workpoint-resource-comparison/spec.md` 的已确认功能规格

## 概要

在现有 AI 多方案比选入口增加桥梁工点单选门禁。初始化请求携带稳定目标工点 ID，后端验证该工点属于当前项目版本且存在合法可调本地资源；LLM 与确定性回退只为该工点的 `WORKPOINT_EXCLUSIVE` 本地池生成数量，其他工点本地池和所有 `PROJECT_SHARED` 池从当前场景逐池原样保留。三套方案继续携带完整资源快照，使用现有全项目任务、逻辑、里程碑和 15 秒严格固定资源入口求解。

目标工点身份写入资源方案，并参与生成、更新、求解、比较、推荐、详情、基准确认和当前性校验。前端切换工点时立即清空旧会话并使用请求序号隔离迟到响应；方案卡只展示和允许编辑目标工点的本地资源。后端同时执行范围校验，拒绝借由接口修改其他工点或共享池。

## 技术上下文

**语言/版本**：Python 3.11；TypeScript 5.7；Node.js 22

**主要依赖**：FastAPI/Pydantic、React 19、OR-Tools CP-SAT、Vite 6

**存储**：本功能不新增数据库或迁移；目标工点身份随现有资源方案/计划快照模型持久化，历史缺失字段按兼容策略读取

**测试**：pytest 后端定向测试；Node `node:test` 前端契约/源码边界测试；TypeScript 类型检查；Vite 生产构建；OpenAPI YAML 解析；`git diff --check`

**目标平台**：本地 FastAPI 服务、Vite/React 前端及现有容器/Netlify 演示部署

**项目类型**：跨前后端 Web 应用与共享 API 契约变更

**性能目标**：不增加求解阶段或改变单方案 15 秒预算；工点选择和资源范围校验相对完整任务生成/CP-SAT 求解为常数或线性资源池遍历开销

**约束**：全项目排程与指标口径不变；只允许目标工点本地池数量变化；共享池逐池冻结；保持 `pool.id` 身份，不按资源类型合并；数量为非负整数且不超过对应 `max_quantity`；旧工点响应不得污染当前会话

**规模/范围**：1 个 AI 多方案页面、1 个方案卡及相关领域函数；AI 助手共享请求/方案模型；初始化、更新、求解、比较/推荐和基准确认边界校验；LLM 上下文/校验/回退/指纹；后端与前端定向测试和 API 基线

## 生命周期归属

- **规格归属引用**：[spec.md#生命周期归属](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/`、`04-demo/backend/app/services/ai_resource_scheduling_assistant.py`、`04-demo/backend/app/services/ai_resource_explainer.py`、`04-demo/backend/app/services/progress_forecast.py`、`04-demo/backend/app/api/routers/assistants.py`（仅在错误映射需要时）、`04-demo/backend/tests/`、`04-demo/frontend/src/contracts/`、`04-demo/frontend/src/features/resourceAssistant/`、`04-demo/frontend/src/domain/resourceAssistant.ts`、`04-demo/frontend/tests/`

## Constitution 检查

*门禁：Phase 0 研究前已通过；Phase 1 设计后再次检查。*

- **可验收需求：通过。** 用户已确认“AI 只调整所选工点资源，仍计算全项目排程”，规格包含选择、冻结、求解、失效、兼容和可衡量验收。
- **显式算法规则：通过。** 输入为完整场景、目标工点和完整资源快照；AI 变量仅为目标工点本地池数量；共享池和其他工点池为固定输入；求解目标、硬约束、里程碑和 15 秒预算不变。
- **显式共享契约：通过。** 设计为初始化请求新增必填目标工点 ID，资源方案新增可兼容读取的目标工点身份；定义 422 错误、空态、迟到响应和历史缺失身份策略。
- **保留行为与最小设计：通过。** 复用现有 `ResourceAssistantPlan`、`ResourcePool`、初始化/更新/求解/比较/推荐端点和页面组件，不新增平行模型、端点、依赖或持久化服务。
- **分阶段价值：通过。** 首批即可完成“选工点—生成三方案—全项目求解—对比/推荐—基准确认”的独立闭环。
- **验证与证据：通过。** 双工点加共享池样例同时验证后端不可绕过范围、全项目任务覆盖、工点切换和历史兼容。
- **资产与数据安全：通过。** 仅在 053 规格目录新增正式设计资产；不移动或删除用户数据、历史方案或其他规格。

## Phase 0：研究结论

无新增阻塞性未知项。实际代码证据和设计决策见 [research.md](./research.md)。关键结论是：范围限制必须由后端初始化、更新与求解边界共同强制；三方案仍保存完整 `resource_pools`，不能把场景或结果裁成单工点。

## Phase 1：设计

### 共享身份与兼容

1. 初始化请求增加必填 `target_workpoint_id`。后端按 `project_data_version_id` 重新投影当前项目主数据快照，从投影后的完整桥梁工点清单按稳定 ID 解析名称并验证其可参与排程；无项目主数据版本时才沿用场景桥梁作为兼容输入。
2. `ResourceAssistantPlan` 增加可空的 `target_workpoint_id` 与 `target_workpoint_name`。新生成方案两者必填；可空仅用于读取历史资源方案和计划快照，历史方案不得直接进入新的单工点生成/更新/求解/确认链路。
3. 目标工点 ID 进入生成记录输入指纹与方案求解输入指纹；三方案比较和推荐要求所有方案目标工点一致。
4. 不新增持久化表。现有计划快照内嵌 `ResourceAssistantPlan`，自然携带新字段；历史 JSON 缺失字段继续可解析。

### AI 生成与确定性回退

1. 从完整场景解析目标工点可调本地池：`scope_mode=WORKPOINT_EXCLUSIVE`、稳定归属目标工点、启用、受限且有合法数量边界。
2. LLM 上下文继续提供全项目画像和完整资源基线用于理解影响，但明确列出唯一 `editable_resource_pools`；输出校验只接受这些池的目标工点数量，拒绝共享池、其他工点、未知池或属性变更。
3. 本地回退只为同一可调集合形成经济、平衡、抢工梯度。若集合为空，初始化返回 422 可行动诊断，不生成占位三方案。
4. 将通过校验的目标工点数量合并回场景完整资源池深拷贝；非目标池逐字段保持原值。合并后再执行现有资源池校验并生成三套完整方案。

### 更新、求解与结果链路

1. 方案卡只渲染目标工点本地资源行；共享池和其他工点不再提供编辑控件。
2. 更新服务按方案目标工点验证 `resource_pool_id + workpoint_id`，拒绝旧 `resource_updates`、共享池、其他工点、未知池、停用池和越界数量。
3. 求解前验证方案目标工点存在且计划中所有非目标资源与当前场景逐池一致；通过后继续用方案完整 `resource_pools` 替换场景资源并调用现有严格固定资源全项目求解。
4. 比较、推荐、详情和基准确认继续使用全项目结果；用户可见说明同时展示“AI 推进工点”和“全项目排程指标”。
5. 基准确认服务拒绝缺失目标工点身份或目标身份与当前项目版本不一致的新链路请求；历史计划仍可只读保留。

### 前端状态与请求隔离

1. 在生成三方案前展示工点下拉，数据复用工作区按 `project_data_version_id` 加载的完整权威桥梁工点清单并按主数据顺序展示；同名选项附带稳定 ID 区分，不再读取旧 `scenario.project.bridges` 作为主数据版本下的下拉来源。
2. 初始不自动选择；无选择、无工点或无合法可调资源时禁用生成并显示对应提示。
3. 目标工点变化时同步清空初始响应、方案、结果、比较、推荐、详情、选中方案、下载上下文和本轮基准状态。
4. 为生成、单方案求解、更新、比较与推荐沿用/补充请求序号或范围令牌；响应落地前核对当前 `scenarioFingerprint + targetWorkpointId`。

### 契约与验证资产

- 数据与状态模型：[data-model.md](./data-model.md)
- API 契约：[contracts/ai-workpoint-resource-comparison.openapi.yaml](./contracts/ai-workpoint-resource-comparison.openapi.yaml)
- UI 行为契约：[contracts/ui-behavior.md](./contracts/ui-behavior.md)
- 端到端验证指南：[quickstart.md](./quickstart.md)

## Constitution 设计后复核

- 设计未改变 CP-SAT 变量、约束、目标顺序、预算或结果指标，算法门禁继续通过。
- 新字段、422 失败态、历史兼容、全项目输出和下游失效均已在数据模型与接口契约中明确，共享契约门禁通过。
- 后端以 `pool.id + workpoint_id` 强制范围并保留完整池快照，满足数据完整性与同类型多池不合并要求。
- 未新增依赖、端点、存储或迁移，未发现需登记的复杂度例外。
- 仓库未提供技能所述的 `update-agent-context` 脚本；现有 `AGENTS.md` 已是项目执行规则唯一来源，本功能不修改 Agent 上下文。

## 项目结构

### 本功能文档

```text
03-requirements/specs/053-ai-workpoint-resource-comparison/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ai-workpoint-resource-comparison.openapi.yaml
│   └── ui-behavior.md
└── tasks.md              # 由 $speckit-tasks 生成
```

### 生命周期与源码结构

```text
04-demo/
├── backend/
│   ├── app/contracts/
│   ├── app/services/ai_resource_scheduling_assistant.py
│   ├── app/services/ai_resource_explainer.py
│   ├── app/services/progress_forecast.py
│   └── tests/
└── frontend/
    ├── src/contracts/
    ├── src/domain/resourceAssistant.ts
    ├── src/features/resourceAssistant/
    └── tests/
```

**结构决策**：继续在既有 AI 资源助手纵向切片内完成共享模型、服务、页面和测试修改；053 目录只承载正式需求与设计资产，不复制业务代码。

## 复杂度跟踪

无 Constitution 违反项，无需复杂度例外。
