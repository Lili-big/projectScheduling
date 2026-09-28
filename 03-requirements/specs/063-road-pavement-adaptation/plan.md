# 实施计划：公路路面首版适配

**工作分支**：`codex/road-pavement-engineering` | **功能目录**：`063-road-pavement-adaptation` | **日期**：2026-09-22 | **规格**：[spec.md](./spec.md)

## 概要

工序关系增量（R1～R5）：在 `contracts/pavement.py` / 前端 `contracts/pavement.ts` 增加可选 `dependency_rules`，沿用本地项目配置保存，无新API/数据库表。后端 `scheduling/generation/pavement.py` 与前端 `domain/pavement.ts` 对启用层和正工期配套构造同样的邻接边/稳定槽位；规则按段优先、统一次之、原条件兜底。零天配套仍累计到原边间歇，显式N是该边完整间歇，不再与原等待相加。非FS不自动变为材料养生；末层养生仍从既有条件取得。

生成有效边后，未配置规则的行为不变；显式FS边将源任务等待改为N，其他关系的源任务结束后等待记0，已确认日期保持。求解器复用已有四类precedence约束，删除无条件重加的相邻层FS，仅对FS边补验收可用下限。保留层序连通性、资源互斥、转场、末层交付和循环诊断。目标仍为最早整体可用，不增加新目标。任务视图必须显示真实关系和N。

工艺逻辑页以实际边表替换静态九行说明。视图可选统一/单段，显示前后工序、关系、N、表达和来源；清空N保存未完善配置，恢复继承删除该条规则。统一模板用类别及同类序号区分水稳底/下/上层；以主数据实际名称显示。配套及末层条件保留在下方折叠区。无启用层/保存失败/无效或未匹配规则保持可见。测试范围为后端generation/solver/config/contracts、前端pavementWorkflow、生产构建和当前8000页面；真实项目只保留用户原参数，不写测试假定值。

宪章检查：输入/公式/优先级/未知值/冲突/兼容/失效/验证均已明确；仅修改既有路径，无新增依赖和存储表。当前技能引用的update-agent-context.ps1不存在，不补建无关脚本；本增量不改变语言、依赖或目录，agent.md既有技术事实仍适用。

2026-09-23 修订：在已有组件参数中增加density_t_m3和单段编辑请求字段，复用保存服务/SQLite，不新增表或新接口。密度省略时保留原值（旧调用方），显式null清空；前端输入直接计算派生吨位，不另存易失真的汇总吨位。当前客户快照按用户范围一次迁移密度到水稳层并移除旧段级统计参数；厚度/启用/长度及所有其他字段保持。主表删3列、各表头单位同行，嵌套层表增密度/吨位，路面隐藏历史卡片，样式收紧仅作用路面。后台仍按长度生成任务，新增材料属性不改变工效、资源及养生规则。

用户后续修订：编辑入口移至主数据表每个施工段的展开行，移除工艺逻辑页模板入口。当前确认版本的空段通过显式POST初始化为默认5层，历史版本只读；单段保存采用新版本+原并发检查/引用保护/结果失效，无新存储表。以基线版本与内容的组合指纹保存编辑，支持用户将数值改回历史值而不违反既有指纹唯一约束；内容无变动直接返回当前版本。空厚度保留为未设置参数，完整性诊断保留。保留已存在层标识、未编辑字段和原段来源；新层分配独立标识。界面保存成功后切换新版本并保留展开施工段。

结构层补齐增量：复用 `ProjectMasterService`、快照校验/差异/指纹、草稿与确认接口，不新增表。新增创建模板草稿接口，服务端深拷贝当前版本，仅向明确选中且没有任何构件的路面段增加层；草稿不影响当前版本，确认沿用并发版本保护及旧结果失效。前端在工艺逻辑页提供按顺序编辑层名/类型/厚度、选段和版本预览，应用成功后重读权威主数据。等待条件仍保存于既有路面场景配置，另提供按工艺只补缺失条件，避免跨两个存储系统的假原子操作。数据层不提供猜测层厚，真实客户分层参数待确认；不新增模板库持久化或通用编辑器。

复用项目主数据版本、工艺工效编辑器、工序配置、资源池、任务/结果页面及失效流程，增加明确的路面对象与日粒度排程。三类核心工艺与机组分别为碎石、水稳、热拌沥青，配套工作按资源充足处理但保留时间。先完成固定机组数量下的端到端计划，不把现有桥梁资源搜索或路径惩罚套用到路面。

## 技术上下文

- **语言/版本**：Python 3.12、TypeScript/React 19；仓库推荐 Node 22，本机启动已使用 Node 24。
- **主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、openpyxl、Vite；无新增运行依赖。
- **存储**：现有项目主数据 SQLite；现有 `scheduler-config.json` 扩展路面按项目配置，不复制主数据；历史桥梁配置保留。
- **测试**：pytest、Node 测试、TypeScript/构建、真实 HTTP、浏览器关键流程及仓库文档/契约校验。
- **目标平台**：当前 Windows 本地 FastAPI/Vite，兼容既有单服务部署契约；不增加部署目标。
- **项目类型**：现有 Web 应用跨主数据、排程与页面的功能扩展。
- **性能目标**：首版验收至少 3 段双幅、各 6 个核心层及必要配套工作；在现有可配置时间预算内返回解或明确状态，不承诺全项目规模的最优性。转场路线建模不得引入无上限外部等待。
- **约束**：没有真实主数据和工效时用明确标注的测试样例；无全仓重命名、无旧数据清理、不改变原桥梁路径行为；用户确认 tasks.md 后才能实施。
- **规模/范围**：四个用户故事，改造五类主流程页面并补必要的结果呈现，新增路面专有规则模块而非另建一套应用。

## 生命周期归属

规格归属引用 [spec.md](./spec.md) 的生命周期段落。实施代码全部进入现有 `04-demo/backend`、`04-demo/frontend` 所有权目录，样例以测试构造数据为主；真实客户资料不复制进实现目录。

## Constitution 检查

| 项目 | 研究前 | 设计后 |
| --- | --- | --- |
| 业务来源、范围与确认 | 已引用原图及两次用户答复 | 三类工艺、三类独立机组明确 |
| 算法语义 | 已明确工期/等待/转场区别 | 输入、目标、硬约束、时间边界与样例齐全 |
| 共享契约 | 明确跨前后端影响 | data-model 与 contracts 定义字段、状态、兼容和失效 |
| 最小设计 | 复用现有应用 | 新文件限路面契约、任务生成、约束和策略等直接职责 |
| 数据安全 | 无迁移或删除授权需求 | 追加对象和配置；保留旧版本与本地状态 |
| 验证 | 规格 SC-001～008 | 自动样例＋真实数据到位后的人工核验分开记录 |

内容门禁通过。现有仓库全局验证未全绿：生命周期检查有 9 个既有缺失引用；requirements.txt 与冻结哈希不一致且本次无该文件 diff。它们不得被“更新基线”掩盖，实施时只确认本次未新增相关失败；核心契约/排程检查失败仍阻止完成。

## 研究结果

见 [research.md](./research.md)。无剩余阻塞性技术未知。缺失真实客户文件不阻塞设计；客户输入映射与真实案例 SC-008 待文件提供后完成。

## 技术设计

### 1. 主数据与导入

增加主数据类型 `pavement`（路面工点）、`pavement_section`（分幅施工段），核心构件 `granular_base`、`cement_stabilized_base`、`asphalt_course`（实际结构层）。已有 `roadbed` 仍为路基，不整体改名。一个工点可以有多个分幅施工段，每个施工段包含有序结构层。

复用现有参数表保存几何、路床可用日期、数量依据和确认状态；不新增平行主数据存储。扩展当前 Excel 为兼容版本 1.2，保留已有四个必需工作表及可选线路关系；用户可见路面模板列给出路段/幅/层含义。原 1.0/1.1 仍可读取。

用户确认的段级水稳统计复用 ParameterValue，增加 `water_stable_thickness_m` 与 `water_stable_density_t_m3` 参数列及导出映射；当前15段按确认值0.76、2.38形成新版本。主数据表由四个数值计算吨位，显示两位小数，缺值或无效尺寸显示“—”；不写入组件工期计算，不覆盖组件级 `thickness_m`。页面精简及工具栏控件修正沿用现有组件与样式。

身份或格式错误阻止导入确认；数据结构合法但施工值尚缺时可形成已确认主数据版本，排程前返回对象级缺项诊断。桩号与净施工长度不同必须经人工确认数量依据后才可用于工期。

### 2. 场景与配置

增加可选 `engineering_domain`，旧请求缺省保持 bridge；前端路面入口显式传 pavement。任务生成不能依据名称猜领域，也不能将未适配工点静默纳入结果。

新增 `pavement_settings` 保存按层引用的养生/验收条件、配套工作和固定顺序；实际几何与工程量权威仍是已确认主数据。工艺库继续使用 ProcessTemplate/ProductivityOption，机组继续使用 ResourcePool。用现有 TaskOverride 选择层级工效，不新造第二套工效机制。

`scheduler-config.json` 追加按 project_id 区分的路面配置区，旧顶层桥梁字段完整保留；路面保存不能触发桥梁默认工艺补齐或资源清理。新增字段在旧领域为空时不输出，以维持既有 dump/稳定指纹；新领域纳入完整指纹。

### 3. 任务、逻辑与日期

`generation/pavement.py` 负责将确定主数据和配置生成核心施工任务、配套任务、逻辑与最早开始条件。geometry 与单位校验先于工期计算。正施工工程量用已存在的向上取整规则，配套作业使用明确固定天数。

施工 Task 仍保持最小 1 天；0 天的配套条件不伪造 1 天任务，用前后条件转接表达。养生使用层间 lag；验收可用日期转换为下游最早开始约束。末层通过单独 readiness 条件参与可交付目标，不伪造占用主设备的养生任务。

时间区间 [start,end)；施工日期显示到 start_date + end - 1，后续可用事件在 start_date + ready_offset。两者的边界显示差异不是额外施工日。ready_offset 为 max(end + wait_days, accepted_available_offset)，样例以同一口径检查。

### 4. 固定资源求解与转场

`application/pavement.py` 编排路面生成、求解与诊断；`solver/strategies/pavement.py` 使用现有命名资源分配和通用先后/最早开工构建函数，调用新增的路面转场约束。共享 `_models.py` 和 `_scenario.py` 只增加字段装配/领域分派，桥梁原路径不改算法。

每套机组在候选任务上构建带虚拟起终点的顺序路径。任务是否进入路径与已有唯一资源分配绑定，选中的实际相邻弧 i→j 强制 start_j >= end_i + transfer_days；仅对不同作业位置（施工段＋幅）计转场。同点换层 0，初次进场及末尾离场不自动加时间。可沿用现有 AddCircuit 技术模式，不复用其跨墩距离惩罚。

转场只绑定真实相邻作业，不对所有两两任务额外计时。结果按所选弧还原转场占用段 [end_i,end_i+transfer_days)，机组在该段不能执行其他任务；设备空闲和养生可并存。

目标最小化整个已启用施工范围的可交付边界。所有移交、工艺、等待、资源和转场限制为硬约束，不启用桥梁 best-effort 放宽。输入错误与物理无解、超时无解分开；预算内仅得可行解时保留 FEASIBLE。

时间上界必须覆盖最晚移交/验收日期、任务工期、等待及最多 N-1 次有效转场，不能继续用仅总工期加 30 天的上界排除远期移交。任务是不可抢占单机组作业，增设备只能增加跨工作面并行。

### 5. 接口、页面与兼容

沿用现有主数据导入/确认接口；模板提供 `engineering_domain=pavement` 可选查询。沿用生成/求解接口，在显式领域中处理新增对象。原请求缺省 bridge、原接口状态语义保持。

路面入口显示主数据、工艺工效、工艺逻辑、关键机组、任务和结果。最少资源/成本优化、桥梁 AI 助手、架梁专项和未适配计划管控不作为路面可用操作；服务端对直接调用同样返回明确不适用诊断。桥梁场景继续保留原入口。简单结果查看/当前求解不依赖外部 AI。

结果展示施工与可用边界、配套工作、养生区间、机组和转场。保存/加载失败不覆盖当前草稿或历史结果，输入变更沿现有指纹机制使任务、求解、比较及下游引用失效。

## 实际修改路径

以下为允许进入 tasks 的目标；不要求每个文件都必须修改，无业务需求不得扩展文件集合。

| 范围 | 路径（均相对仓库根目录） |
| --- | --- |
| 后端领域契约 | `04-demo/backend/app/contracts/pavement.py`（新增）、`contracts/_models.py`、`contracts/project_master.py`、`contracts/__init__.py`（后续同表后端缩写以 `04-demo/backend/app/` 为根） |
| 主数据 | `project_master/definitions.py`、`workbook.py`、`validation.py`、`scheduling_adapter.py`、`service.py`、`repository.py`、`schema.py`（仅必要兼容项）、`diff.py` |
| 场景和规则 | `scheduling/generation/pavement.py`（新增）、`scheduling/application/pavement.py`（新增）、`scheduling/application/_scenario.py`、`scheduling/domain/resource_scope.py`、`scheduling/domain/milestone_scope.py`、`process_library_defaults.py`、`local_scenario_config.py`、`services/process_library_service.py`、`scenario_data.py` |
| 求解 | `scheduling/solver/constraints/pavement.py`（新增）、`scheduling/solver/strategies/pavement.py`（新增）、`scheduling/solver/engine.py`、`scheduling/solver/results.py` |
| HTTP | `api/routers/project_master.py`、`api/routers/scheduling.py`、`api/routers/system.py`、`api/routers/assistants.py`、`api/errors.py` |
| 前端契约/API | `04-demo/frontend/src/contracts/pavement.ts`（新增）、`contracts/scheduler.ts`、`contracts/projectMaster.ts`、`contracts/index.ts`、`api/_schedulerApi.ts`、`api/projectMasterApi.ts`、`api/scenarioApi.ts`、`api/schedulingApi.ts`（后续同表前端缩写以 `04-demo/frontend/src/` 为根） |
| 前端领域/装配 | `domain/pavement.ts`（新增）、`domain/projectMaster.ts`、`domain/productivity.ts`、`domain/resources.ts`、`domain/logic.ts`、`domain/milestones.ts`、`domain/constants.ts`、`domain/labels.ts`、`domain/scenarioMutations.ts`、`app/Workspace.tsx`、`app/useWorkspaceController.ts`、`app/workflows/scenarioWorkflow.ts`、`app/workflows/solveWorkflow.ts` |
| 页面 | `features/projectMasterData/ProjectMasterDataWorkspace.tsx`、`WorkPointList.tsx`、`WorkPointDetail.tsx`、`ImportPreview.tsx`；`features/process/ProcessTab.tsx`、`features/logic/LogicTab.tsx`、`features/resources/ResourcesTab.tsx`、`features/taskView/TaskViewWorkspace.tsx`、`features/scheduleResults/ScheduleResultsWorkspace.tsx`、`features/scheduleResults/presenter.ts`、`features/layout/WorkspaceNavigation.tsx` |
| 后端测试 | `04-demo/backend/tests/test_pavement_contracts.py`、`test_pavement_master.py`、`test_pavement_generation.py`、`test_pavement_solver.py`、`test_pavement_api.py`、`test_pavement_config.py`（新增）；邻近既有主数据/调度/架构测试及架构基线 |
| 前端测试 | `04-demo/frontend/tests/pavementWorkflow.test.mjs`、`pavementResults.test.mjs`、`pavementMaster.test.mjs`（新增）；邻近既有契约/资源/结果测试及架构基线 |
| 未部署镜像 | `04-demo/tools/demo-api-mirror/api.mts`：声明不支持路面新领域并明确拒绝，不能回退生成桥梁结果，不扩建第二套路面求解实现 |
| 文档 | `README.md`、`agent.md`、`04-demo/README.md`、`03-requirements/specs/README.md` 和本规格目录 |

## 验证与交付顺序

1. 共享契约先落地并建立旧请求兼容测试。
2. US1 主数据可以独立导入、确认、追溯。
3. US2 工效可复算，US3 任务链及日期条件可检查。
4. US4 三类机组、转场、求解和结果完成端到端闭环。
5. 各批次最小验证通过后，运行一次全量后端、前端测试及构建；最后执行 HTTP/浏览器验证和契约/治理校验，不重复同一全量检查。
6. 真实数据提供后进行 SC-008；记录在 quickstart 的客户验证段，不以自动样例替代。

## 已知环境检查与上下文更新

创建规格时已执行仓库、生命周期和文档检查：文档通过；其余既有失败见 research.md。本轮未修改业务代码或依赖。

仓库没有 `update-agent-context.ps1` 或同名替代脚本；不新造执行入口，直接在已有 `agent.md` 留下本规格链接和待实施状态。此为缺失辅助脚本的最小替代，不改变项目工作契约。

## 复杂度跟踪

无宪章违反项。独立路面生成/约束/策略文件用于避免把新增规则继续堆入桥梁引擎；复用现有 API、资源及结果契约，不建立第二套系统。
