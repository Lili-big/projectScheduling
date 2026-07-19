# 实施计划：工点主导资源配置与范围共享流转

**分支/目录**：`048-workpoint-first-resource-allocation` | **日期**：2026-07-18 | **规格**：`03-requirements/specs/048-workpoint-first-resource-allocation/spec.md`

**输入**：来自当前功能目录的 `spec.md`，以及 047 已完成规格、现行产品文档、规则文档和真实代码/测试。

## 概要

在不创建第二套资源权威模型的前提下，继续以 `ScenarioInput.resource_pools` 为统一持久化和求解输入，但将列表语义从“每种资源类型只能一个池”调整为“每个池以稳定 `pool.id` 唯一，同类型可以有多个独立池”。`ResourcePool` 增加显式 `workpoint_id`；新建工点本地资源使用 `WORKPOINT_EXCLUSIVE + workpoint_id` 单工点池表达，范围共享资源使用 `PROJECT_SHARED` 池表达。旧项目共享池原样保留为一个共享池；047 多工点独享池仅在有效值可无损展开时标准化为单工点池，否则阻断迁移并保留原数据。

任务先按工艺获得资源类型，再合并任务工点的本地实例与所有范围匹配的共享实例。当前资源模式只展开 `quantity`；数量为 0 且没有合法共享候选时输出工点、任务、资源类型三级阻断诊断。增配与最少资源分析继续以 `max_quantity` 为上界，但建议未采纳前不改变当前计划。求解器复用现有按命名实例的互斥和按 `pool_id` 的资源组，不新增人工顺序、转场变量、目标项或依赖。

前端改为工点一级导航和独立共享池区域；资源目录由当前工艺资源类型与既有池元数据形成只读投影，不新增本期目录管理。AI、计划快照、结果展示、指纹和旧结果失效全部改为按 `pool.id` 保留同类型多池身份。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript 5；Node.js 22 发布基线

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite；不新增依赖

**存储**：`ScenarioInput.resource_pools`、`.local-data/state/scheduler-config.json`、AI 资源方案和计划管控 JSON 快照；沿用现有标准序列化和稳定指纹

**测试**：pytest、Node `--test`、前端 typecheck/Vite build、真实浏览器组件测试、API/架构契约测试、`verify:architecture`、文档门禁

**目标平台**：本地 FastAPI + React 工作台、单服务演示、现有 Docker/Netlify 构建链

**项目类型**：跨前后端 Web 应用、共享资源契约、任务候选和 CP-SAT 求解联动

**性能目标**：在现有典型约 1586 任务规模和现有求解时间预算内，工点/共享池标准化与候选筛选不成为求解主耗时；页面切换工点不得触发 N×W 串行请求；同类型多池不得引入按名称的全表回查

**约束**：不新增第二套顶层资源权威；不解析名称或 ID 格式判断作用域；不修改既有求解目标和优先级；共享转场时间/成本均为 0；不新增人工流转顺序；不配置架桥机和梁场；不新增依赖

**规模/范围**：共享模型、资源标准化、命名实例、候选诊断、三类求解身份、资源配置页、AI 资源助手、本地配置、计划快照/指纹、结果说明及对应自动化测试

## 生命周期归属

- **主要阶段**：`03-requirements`
- **工作包**：`048-workpoint-first-resource-allocation`
- **资产类型**：Spec Kit 正式成果
- **跟踪策略**：`tracked`
- **保留类别**：`formal-output`
- **主归属**：`03-requirements/specs/048-workpoint-first-resource-allocation/`
- **跨阶段引用**：实现和测试仍归 `04-demo/bridge-scheduling-demo`；本目录只定义规格、设计、契约、验收和任务，不复制代码或运行证据。

## Constitution 检查

### Phase 0 前

- [x] 用户已确认产品口径并由 G00 建立 `048-workpoint-first-resource-allocation` 正式工作项。
- [x] `spec.md` 已引用产品文档、规则、047 规格和真实前后端/求解代码事实。
- [x] 输入、输出、数量 0、候选、互斥、三类求解、迁移、异常和验收场景均可测试。
- [x] 工点本地资源、范围共享池和旧项目共享配置均保持一个权威 `resource_pools` 列表，不创建平行顶层模型。
- [x] 共享转场 0 天/0 成本被明确为本期限制，不提升为长期真实调拨模型。
- [x] 规格资产归属、跟踪策略、保留类别和 Demo 跨阶段引用已声明。
- [x] 全部 Spec Kit 文档使用中文简体；代码标识符、字段、路径和命令保持原文。
- [x] 不移动现有资产，不修改 README，不提交 Git。

### Phase 1 后

- [x] `research.md` 已收敛统一模型、迁移、候选、数量、AI、持久化和页面决策，无 `NEEDS CLARIFICATION`。
- [x] `data-model.md` 为每个实体定义身份、不变量、兼容输入和状态转换。
- [x] `contracts/workpoint-resource-allocation.openapi.yaml` 只扩展现有端点和 schema，不创建平行 API。
- [x] `quickstart.md` 覆盖工点维护、目录补充、数量 0、多共享池重叠、互斥、零转场、AI/指纹和旧共享兼容。
- [x] 计划不包含 Constitution 违反项；现有模块足以承载实现。
- [x] 当前仓库没有可执行的 agent-context 更新脚本，本阶段不改 `agent.md`，避免越过用户未授权的公共文档范围。

## 项目结构

### 本功能文档

```text
03-requirements/specs/048-workpoint-first-resource-allocation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── workpoint-resource-allocation.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 预期实施位置

```text
03-requirements/product/
  资源配置页面需求文档_v1.2.md                  # 同步工点主导页面和独立共享池口径
03-requirements/rules/
  工点级资源作用域与求解规则需求文档_v1.0.md    # 同步多池、数量 0 和零转场规则
04-demo/backend/app/contracts/
  _models.py                                  # ResourcePool/Resource/AI 结果契约
04-demo/backend/app/scheduling/domain/
  resource_scope.py                           # 统一标准化、迁移和有效池解析
04-demo/backend/app/scheduling/application/
  _scenario.py                                # 任务类型、实例展开、缺口诊断和结果摘要
04-demo/backend/app/scheduling/solver/
  engine.py                                   # 按 pool_id 分组、候选和互斥复核
04-demo/backend/app/
  local_scenario_config.py                    # 旧配置兼容与标准保存
  scenario_data.py                            # 资源目录元数据投影
04-demo/backend/app/services/
  ai_resource_scheduling_assistant.py         # 按 pool_id 的建议、校验和结果身份
  ai_resource_explainer.py                    # 多池解释
  ai_parameter_assistant.py                   # 参数建议按池身份定位复核
  plan_control_repository.py                  # 稳定指纹和快照
  progress_forecast.py                        # 计划资源快照兼容
04-demo/frontend/src/contracts/
  scheduler.ts                                # 前端共享类型
04-demo/frontend/src/domain/
  resources.ts                                # 工点/共享池投影、标准化和指纹
04-demo/frontend/src/features/resources/
  ResourcesTab.tsx                            # 工点一级页面和独立共享池区
  styles.css
04-demo/frontend/src/features/resourceAssistant/
  ResourcePlanCard.tsx
  ResourceAssistantPanel.tsx                  # pool.id 级编辑与展示
04-demo/frontend/src/domain/
  resourceAssistant.ts                        # 多池标签与建议身份
04-demo/frontend/src/features/scheduleResults/
  presenter.ts
  ScheduleResultsWorkspace.tsx                # 来源池、工点和零转场说明
04-demo/frontend/src/app/
  Workspace.tsx                               # 增删改池、版本隔离和结果失效
  useWorkspaceController.ts                   # 跨输出失效
04-demo/frontend/src/features/planControl/
  PlanControlPanel.tsx                        # 调整目标按池定位
04-demo/tools/demo-api-mirror/
  api.mts                                     # 未部署参考镜像契约同步
04-demo/backend/tests/
04-demo/backend/tests/scheduling/
04-demo/frontend/tests/
```

**结构决策**：保留 `ResourcePool`、`Resource`、现有保存/生成/求解/AI 端点和 `NoOverlap` 路径。新增能力通过“池 ID 唯一、资源类型可重复、单工点本地池 + 多范围共享池”的约束表达。D06 先冻结共享契约，D02 再修改解析和求解路径；D05、D07、D04 在契约稳定后分别接入页面、AI 和计划快照，最终由 D06 执行一次 R3 全量门禁。

## 设计与实施阶段

### Phase 0：研究与口径冻结

- 记录当前 047 的单类型唯一假设、按类型汇总漂移和可复用的命名实例互斥。
- 冻结新配置的不变量：池 ID 唯一、工点本地池单工点、共享池可多实例/多范围、旧共享池不拆分。
- 冻结数量 0 与三类求解边界，避免实现阶段重新解释。

### Phase 1：共享契约和兼容标准化

- 允许 `resource_pools` 中资源类型重复，但要求 `pool.id` 全局唯一。
- 新建本地池采用 `WORKPOINT_EXCLUSIVE + 显式 workpoint_id + 无 authorized/overrides`；新建共享池采用 `PROJECT_SHARED + workpoint_id=null + null/显式 authorized 集合 + 无 overrides`。
- 读取 047 多工点独享池时使用现有有效值解析器无损展开；无法展开时保留输入并返回阻断诊断。
- 旧 `PROJECT_SHARED` 池保持 ID、数量、上限、状态、日历、成本和范围。

### Phase 2：任务生成和求解

- 按资源类型收集多个池，再按任务工点过滤本地和共享候选。
- 当前资源只展开 `quantity`；本地数量 0 且无正数量共享候选时产生明确阻断。
- 最大资源/最少资源使用每个池自己的 `max_quantity`，所有统计和建议按有效池 ID 返回。
- 继续复用命名实例互斥，不创建转场区间、前置、成本或人工顺序。

### Phase 3：持久化、AI 和计划快照

- 本地配置按 ID 合并同类型多池，标准化后稳定排序。
- AI 旧“类型→数量”仅在该类型唯一对应一个共享池时兼容；其他情况必须使用 `resource_pool_id` 精确更新。
- 计划快照、预测、资源助手结果和稳定指纹保留每个池身份与工点范围；类型相同但池不同不得折叠。

### Phase 4：工点主导页面和结果体验

- 工点页按权威工点选择，默认资源由任务/工艺需求投影，从资源目录补充时创建单工点本地池。
- 页面提供本地资源数量/上限/状态编辑，不提供适用工点勾选。
- 独立共享池区支持同类型多池增删改和范围选择；“全部工点”与显式集合、空集合明确区分。
- 结果和 AI 页面按池展示来源、分配工点、当前/建议数量及 0 天/0 成本提示。

### Phase 5：集成与唯一发布门禁

- 定向测试先覆盖契约、迁移、求解、AI、计划和页面；各领域只跑最小风险门禁。
- 在发布门禁前同步两份来源需求文档，使产品/规则权威口径与 048 规格及实际实现一致。
- D06 在所有定向证据完成后独立重跑一个最高风险贯通样例，并集中执行本功能唯一一次后端全量、前端全量、typecheck、build、架构和文档门禁。

## 验证策略

- **契约**：旧共享 schema、新单工点池、同类型多共享池、重复 ID、空范围和 AI pool-id 更新。
- **算法**：本地+共享候选并集、范围外 0 候选、数量 0 阻断、共享实例互斥、三类数量边界和每池结果身份。
- **前端**：工点一级维护、目录补充、无反向勾选、共享池 CRUD、版本晚到、保存失败重试和结果失效。
- **兼容**：旧共享池不拆分且全字段保真；047 多工点独享仅无损展开；不修改历史快照原文。
- **横切**：AI/计划/结果不按类型折叠，硬编码扫描无名称/ID 特例，排除项无新增字段或入口。

## 复杂度跟踪

无 Constitution 违反项。允许同类型多 `ResourcePool` 是复用既有统一模型的最小变化；另建 `workpoint_resource_configs` 与 `shared_resource_pools` 两个顶层权威列表会增加迁移、端点、AI 和快照漂移风险，已拒绝。
