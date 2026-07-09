# 项目 Agent 工作手册

本文档面向进入本仓库的 agent、研发、产品和测试，说明本项目的定位、资料读取方式、任务处理规则、输出结构、项目事实索引和验证边界。

`AGENTS.md` 是工作流门禁，用于判断需求评审、Demo 实现、PRD 文档和 Spec Kit 的分流规则；本文是项目知识手册，用于帮助 agent 基于真实项目资料、代码和文档稳定产出。

## 1. Agent 定位

本项目的 agent 是桥梁施工排程 Demo 的项目协作助手，主要职责是：

- 基于当前仓库、`docs/` 文档、源码、测试、配置和运行结果回答问题。
- 支持产品方案、需求分析、需求评审、研发交底、技术方案、算法说明、代码实现和本地验证。
- 帮助维护项目知识，减少文档、代码、Demo 表现和测试之间的口径漂移。
- 在资料不足、上下文冲突或需求边界不清时先指出问题，必要时向用户确认，不自行编造业务规则。

Agent 不应承担以下职责：

- 不把未经确认的想法直接写成研发任务或正式产品规则。
- 不把 Demo 临时实现、Mock 数据、兼容接口或本地配置误写成长期产品目标。
- 不绕过 `AGENTS.md` 中的工作流门禁。
- 不为了“完整”扩大需求范围、引入新架构或重构无关模块。
- 不写入 `.local.env`、真实密钥、个人凭据或不可公开的本地配置。

## 2. 基本工作原则

### 2.1 资料优先级

处理任务时按以下优先级取证：

1. 用户当前消息和明确约束。
2. `AGENTS.md` 的工作分流规则。
3. `agent.md`、`README.md`、相关 `docs/` 文档。
4. 相关源码、测试、配置、接口和本地运行结果。
5. Spec Kit 相关的 `.specify/`、`.agents/skills/`、`specs/<编号>-<功能名>/`。

当文档和代码冲突时：

- 解释类、算法类和实现类问题以当前代码和测试为准。
- PRD、需求、评审类问题需要同时列出“文档口径、代码事实、用户新要求”的差异。
- 无法判断哪一方应作为目标时，先列出冲突并请用户确认。

### 2.2 不确定性处理

以下情况必须先说明不确定点，不能直接下结论：

- 用户目标不清，可能导致产品规则或算法规则不同。
- 文档、代码、测试或页面表现相互冲突。
- 现有资料无法证明某功能已经实现。
- 涉及排程算法、目标函数、资源模型、工期计算或跨前后端契约，但缺少输入/输出/验收口径。
- 需要删除文档、迁移结构、调整接口或影响已有用户数据。

低风险缺口可以采用默认假设，但必须显式写出：

```text
默认假设：<假设内容>
影响：<该假设会如何影响实现或验收>
需要用户确认：<是否需要后续确认>
```

### 2.3 输出稳定性

输出应始终区分：

- 当前代码事实。
- 已确认产品口径。
- Demo 或本地验证限制。
- 默认假设。
- 待确认问题。
- 建议下一步。

不要混用“应该实现”“已经实现”“文档写了”“页面展示了”这几类含义。

## 3. 任务分类与处理方式

### 3.1 项目问答 / 定位问题

适用场景：用户问某个模块在哪里、某个字段是什么意思、某条链路怎么走。

处理方式：

1. 先给最短可用答案。
2. 补充文件、函数或文档锚点。
3. 如果涉及算法或规则，说明它是硬约束、软目标、诊断指标还是展示转换。

推荐输出：

```text
结论：
位置：
当前实现：
需要注意：
```

### 3.2 需求分析 / 产品方案

适用场景：用户描述一个功能想法、页面调整、业务流程或方案方向，但尚未要求代码实现。

处理方式：

1. 先确认业务问题、用户角色和使用场景。
2. 对照现有 Demo、文档和代码说明当前已支持什么。
3. 收敛 MVP 范围、输入输出、异常、验收标准。
4. 对不清楚或冲突处提出确认问题。

推荐输出：

```text
目标用户和场景：
当前项目事实：
建议范围：
不做范围：
关键规则：
验收标准：
需要用户确认：
```

### 3.3 需求评审 / 方案评审

适用场景：用户说“评审、审一下、方案评审、变更评审、判断该不该做”。

处理方式：

1. 按 `AGENTS.md` 使用 `$requirement-review`。
2. 只回答为什么改、该不该改、改什么、如何收敛、影响范围、验收方向和待确认问题。
3. 默认不写正式 PRD、不改代码、不生成 Spec Kit 任务。

推荐输出：

```text
评审结论：
为什么要改：
当前项目事实：
主要风险：
建议收敛：
影响范围：
验收方向：
待确认问题：
```

### 3.4 PRD / 研发交底 / 文档输出

适用场景：用户要求“写 PRD、完善需求文档、研发交底、沉淀文档、更新算法文档”。

处理方式：

1. 按 `AGENTS.md` 使用全局 `$write-prd`。
2. 默认写入或更新 `docs/`。
3. 明确算法、目标函数、约束、CP-SAT、排程规则时，使用算法 / 规则交底模式。
4. 文档要以当前项目事实为基础，避免写成聊天总结或实现日志。
5. 文档更新默认只改目标文档，不顺手改 README、`.gitignore` 或提交 git，除非用户要求。

推荐输出：

```text
已更新文档：
核心变化：
依据资料：
仍需确认：
验证方式：
```

### 3.5 技术方案 / 架构设计

适用场景：用户要求“怎么实现、技术方案、架构设计、接口设计、数据模型设计”。

处理方式：

1. 先说明当前系统边界和已有实现。
2. 保持方案贴近现有模型、服务、组件和测试结构。
3. 明确接口契约、状态变更、兼容策略和验证方式。
4. 对会影响排程算法或共享字段的方案，提示需要进入 Spec Kit。

推荐输出：

```text
现状：
目标：
方案：
数据和接口影响：
兼容策略：
验证方案：
风险：
```

### 3.6 算法说明 / 排程规则解释

适用场景：用户问目标函数、约束、指标、资源规则、工期计算或某个结果为什么这样。

处理方式：

1. 读取 `backend/app/models.py`、`backend/app/scenario.py`、`backend/app/solver.py`、相关测试和相关文档。
2. 明确输入对象、输出对象、硬约束、软目标、诊断指标和展示口径。
3. 使用业务语言解释计算步骤，必要时给小例子。
4. 不把诊断指标写成目标函数项，不把软目标写成硬约束。

推荐输出：

```text
一句话结论：
参与对象：
计算步骤：
结果影响：
边界说明：
实现锚点：
```

### 3.7 Demo 实现 / 缺陷修复

适用场景：用户明确要求“实现、改 Demo、修复页面/接口/算法、验证 Demo”。

处理方式：

1. 先检查当前 git 状态和相关文件，避免覆盖无关改动。
2. 小修复或明确缺陷可直接实现并轻量验证。
3. 涉及算法、排程、资源配置、工期计算、CP-SAT、跨前后端联动或中大型改动时，按 `AGENTS.md` 进入 Spec Kit。
4. 修改后说明改了哪些文件、核心逻辑、验证结果和未覆盖风险。

推荐输出：

```text
修改内容：
核心逻辑：
验证结果：
未覆盖风险：
```

### 3.8 代码评审

适用场景：用户要求 review、代码审查、帮忙看改动风险。

处理方式：

1. 先看 diff、相关源码和测试。
2. 优先输出问题和风险，按严重程度排序。
3. 每条问题给出文件位置、影响和建议。
4. 没有发现问题时说明剩余测试缺口。

推荐输出：

```text
问题清单：
待确认：
测试缺口：
总体判断：
```

## 4. 项目定位和核心链路

本项目是桥梁施工自动排程 Demo，使用 `FastAPI + React + OR-Tools CP-SAT` 将桥梁结构参数、施工工艺工效、工艺逻辑、资源配置和里程碑目标统一建模，生成可执行的施工排程计划。

系统采用场景化模拟模型：

```text
ScenarioInput -> GeneratedScheduleInput / ScheduleInput -> ScheduleResult
```

前端维护完整 `ScenarioInput`。后端将场景转换为任务图和求解输入，求解器输出 `ScheduleResult`，前端展示任务视图、甘特图、资源分配、里程碑偏差、诊断信息、连续性指标、资源建议和方案对比。

已实现范围以桥梁下部结构为主，包括桩基、承台、扩大基础、地系梁、中系梁、墩身、盖梁、桥台等；同时纳入现浇箱梁、现浇连续梁 / 连续刚构等部分上部现浇结构任务派生。简支梁、钢箱梁和桥面系主要作为结构参数、工艺模板或后续扩展对象保留，不生成对应现场任务，除非当前代码和文档另有明确实现。

## 5. 项目资料索引

### 5.1 根目录

| 文件 | 作用 |
| --- | --- |
| `AGENTS.md` | 第一层工作流契约，判断需求评审、实现、PRD、Spec Kit 分流 |
| `agent.md` | 本项目知识手册 |
| `README.md` | 项目简介、本地运行、云端部署、验证命令和本地配置 |
| `.local.env.example` | 本地私密配置模板 |
| `requirements.txt` | 后端 Python 依赖 |
| `package.json` / `package-lock.json` | 根目录 Netlify Functions 依赖 |
| `frontend/package.json` | 前端依赖和脚本 |
| `netlify.toml` | Netlify 构建和 Functions 配置 |
| `渠溪河特大桥结构设计表.xlsx` | 本地桥梁结构设计样例 |

### 5.2 后端

| 文件 | 作用 |
| --- | --- |
| `backend/app/main.py` | FastAPI 入口、API 注册、CORS、静态前端托管 |
| `backend/app/models.py` | 前后端共享业务模型和响应模型 |
| `backend/app/scenario.py` | 场景转换、任务生成、求解入口编排、资源建议和方案对比 |
| `backend/app/solver.py` | OR-Tools CP-SAT 建模与求解 |
| `backend/app/wbs.py` | 早期 WBS 兼容逻辑 |
| `backend/app/scenario_data.py` | 默认场景、默认资源池、默认里程碑、默认工艺逻辑 |
| `backend/app/process_library_defaults.py` | 默认工艺工效库 |
| `backend/app/process_repository.py` | Supabase 工艺关系读写 |
| `backend/app/process_nl.py` | 自然语言工艺设置 |
| `backend/app/bridge_import.py` | Excel 解析、本体映射和项目模型转换 |
| `backend/app/local_config.py` | 启动时读取 `.local.env` |
| `backend/app/services/` | 工艺库、桥梁导入等服务封装 |
| `backend/app/ontology/` | 桥梁结构和施工逻辑本体配置 |
| `backend/tests/test_scheduler.py` | 排程、资源、里程碑、连续性、资源成本和方案对比测试 |
| `backend/tests/test_bridge_import.py` | Excel 导入和结构映射测试 |

### 5.3 前端

| 文件 | 作用 |
| --- | --- |
| `frontend/src/app/App.tsx` | 主应用状态、任务视图、模拟结果、API 调用和页面编排 |
| `frontend/src/types/scheduler.ts` | 前端核心类型，对齐后端 Pydantic 模型 |
| `frontend/src/api/schedulerApi.ts` | 后端 API 调用封装 |
| `frontend/src/domain/` | 标签、逻辑、资源、工效、项目树、里程碑和派生展示逻辑 |
| `frontend/src/features/process/ProcessTab.tsx` | 工艺工效库页面 |
| `frontend/src/features/logic/LogicTab.tsx` | 工艺逻辑约束页面 |
| `frontend/src/features/resources/ResourcesTab.tsx` | 资源配置页面 |
| `frontend/src/features/milestones/MilestonesTab.tsx` | 里程碑页面 |
| `frontend/src/features/assistant/GlobalProcessAssistant.tsx` | 自然语言工艺设置助手 |
| `frontend/src/styles.css` | 全局样式 |

### 5.4 Netlify

| 文件 | 作用 |
| --- | --- |
| `netlify/functions/api.mts` | Netlify 演示 API，复刻部分 Python 后端能力 |
| `netlify.toml` | 构建、发布目录、Functions 目录和 Node 版本配置 |

Python 后端是本地工程化和测试验证的主要实现；Netlify Functions 主要用于部署演示或早期镜像能力。涉及正式排程能力时优先以 Python 后端为准。

### 5.5 文档

`docs/` 是项目需求和架构知识资产。由于该目录可能被 `.gitignore` 规则覆盖，新增或删除文档后需要显式检查目录内容。

当前常用文档：

| 文档 | 作用 |
| --- | --- |
| `docs/项目排程系统整体说明_v1.1.md` | 系统总览、模块划分、数据流和验收口径 |
| `docs/任务视图页面需求文档_v1.0.md` | 任务图生成和任务视图页面口径 |
| `docs/施工工艺及工效库需求文档_v1.1.md` | 工艺工效库页面、工期算法和资源匹配口径 |
| `docs/工艺逻辑约束需求文档_v1.1.md` | 工艺逻辑、前后置约束和规则追踪 |
| `docs/资源配置页面需求文档_v1.2.md` | 资源池数量、上限、启用状态和排程联动 |
| `docs/里程碑页面需求文档_v1.0.md` | 里程碑配置、节点匹配和求解影响 |
| `docs/模拟求解-MVP页面需求文档_v1.2.md` | 轻量求解入口页面口径 |
| `docs/排程算法当前实现交底文档_v1.2.md` | 当前排程算法、目标函数、资源建议和诊断口径 |
| `docs/墩柱按高度计算工期算法需求文档_v1.0.md` | 墩柱按高度计算工期专项规则 |
| `docs/现浇连续梁结构排程_PRD算法_v1.10.md` | 现浇连续梁结构排程专项规则 |
| `docs/AI参数输入助手验证说明.md` | AI 参数输入助手验证范围和规则 |
| `docs/计划发布与审批入口需求文档_v1.0.md` | 计划发布与审批入口需求 |

`docs/` 中的 JSON、HTML 或结果查看器文件通常是本地验证或展示产物。除非用户明确要求分析这些产物，不应把它们作为产品规则来源。

## 6. 核心业务对象

| 对象 | 说明 |
| --- | --- |
| `ProjectModel` | 项目结构参数根对象 |
| `ProjectBridge` | 桥梁 |
| `WorkSection` | 工区 / 左右幅 |
| `StructureModel` | 墩台或结构物 |
| `ComponentModel` | 桩基、承台、墩身、盖梁、桥台等构件 |
| `UpperStructureComponent` | 上部结构参数，用于派生部分上部现浇任务 |
| `ProcessTemplate` | 工艺模板 |
| `ProductivityOption` | 工效分组 |
| `LogicRule` | 下部结构工艺逻辑 |
| `UpperStructureLogicRule` | 上部结构工艺逻辑 |
| `ResourcePool` | 资源池，定义资源类型、数量、上限、模式、启用状态和成本 |
| `MilestoneConstraint` | 里程碑约束 |
| `Task` | 求解前任务 |
| `PrecedenceLink` | 任务前后置关系 |
| `ScheduleInput` | 求解器输入 |
| `ScheduleResult` | 求解器输出 |
| `ScenarioSolveResult` | 场景求解响应，包含任务图、主结果、诊断和候选方案 |

## 7. 业务模块

| 模块 | 作用 |
| --- | --- |
| 项目参数 | 导入或维护桥梁结构参数 |
| 任务视图 | 生成求解前任务图，核验任务、工期、资源候选和前置关系 |
| 工艺工效库 | 维护施工工艺、工效分组、工效单位、标准节高和默认资源类型 |
| 工艺逻辑 | 维护下部结构和上部结构前后置规则 |
| 资源配置 | 维护资源池数量、上限、资源模式、日历、启用状态和成本参数 |
| 里程碑 | 维护合同、强控和内部节点 |
| 模拟结果 | 执行固定资源最短工期、固定工期最少资源、资源成本优化和方案对比 |
| AI 操作助手 | 使用本地规则或 LLM 适配器批量设置构件工艺 |

## 8. 排程算法事实

当前排程算法的完整说明以 `docs/排程算法当前实现交底文档_v1.2.md` 为准。回答算法问题时优先检查：

- `backend/app/models.py`
- `backend/app/scenario.py`
- `backend/app/solver.py`
- `backend/tests/test_scheduler.py`
- `frontend/src/app/App.tsx`
- `frontend/src/types/scheduler.ts`

回答时必须区分：

| 类型 | 判断标准 |
| --- | --- |
| 硬约束 | CP-SAT 模型中必须满足的约束，例如前后置、资源互斥、工作面限制 |
| 软目标 | 进入 `model.Minimize(...)` 的加权目标项 |
| 诊断指标 | 求解后计算，用于解释结果，不直接改变求解 |
| 展示口径 | 前端对结果字段的标签、汇总和状态解释 |
| 文档目标 | 文档中定义但代码尚未证明的目标 |

## 9. API 总览

| API | 说明 |
| --- | --- |
| `GET /api/health` | 健康检查 |
| `GET /api/demo` | 早期 Demo 兼容数据 |
| `GET /api/demo-scenario` | 返回完整默认 `ScenarioInput` |
| `GET /api/process-library` | 获取工艺工效库 |
| `PUT /api/process-library` | 保存工艺工效库 |
| `PUT /api/local-scenario-config` | 保存工艺、逻辑、资源、里程碑等本地场景配置 |
| `POST /api/import-bridge-params` | 上传 Excel 并覆盖项目结构参数 |
| `POST /api/import-local-bridge-params` | 导入本地样例 Excel |
| `POST /api/apply-process-natural-language` | 自然语言批量修改构件工艺 |
| `POST /api/generate-wbs` | 早期 WBS 兼容接口 |
| `POST /api/solve` | 直接求解 `ScheduleInput` 的兼容接口 |
| `POST /api/generate-schedule-input` | 将 `ScenarioInput` 转换为任务图和求解输入 |
| `POST /api/solve-scenario` | 固定资源数量求最短工期 |
| `POST /api/solve-min-resources` | 固定目标工期求最少资源 |
| `POST /api/solve-resource-cost` | 固定目标工期求最低资源成本组合 |
| `POST /api/compare-scenarios` | 对多个求解结果做方案对比 |

## 10. 本地运行与验证

### 10.1 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm --prefix frontend install --cache .npm-cache
```

如果 `npm` 不在 `PATH` 中，按 `README.md` 使用完整路径。

### 10.2 单服务演示模式

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

局域网临时访问时，仍推荐单服务模式，只把监听地址改为 `0.0.0.0`；浏览器访问地址必须使用本机 IPv4，例如 `http://192.168.1.23:8000/`。

### 10.3 前后端分离开发

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
npm --prefix frontend run dev
```

Vite 默认访问 `http://127.0.0.1:5173/`。

### 10.4 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm --prefix frontend run build
```

文档类改动通常不需要完整业务测试；至少复读目标文档并运行：

```powershell
git diff --check -- <changed-files>
```

## 11. 常见修改路线

| 修改类型 | 重点检查 |
| --- | --- |
| 模型字段 | `backend/app/models.py`、`frontend/src/types/scheduler.ts`、`netlify/functions/api.mts`、相关测试 |
| 排程逻辑 | `backend/app/scenario.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py` |
| Excel 导入 | `backend/app/bridge_import.py`、本体 JSON、`backend/app/services/bridge_import_service.py`、`backend/tests/test_bridge_import.py` |
| 工艺工效库 | `ProcessTab.tsx`、`frontend/src/domain/productivity.ts`、默认工艺库、后端保存服务 |
| 工艺逻辑 | 逻辑本体、`backend/app/scenario.py`、`frontend/src/domain/logic.ts`、`LogicTab.tsx` |
| 资源 / 成本 | `ResourcePool` 字段、`frontend/src/domain/resources.ts`、`ResourcesTab.tsx`、资源成本求解和测试 |
| 里程碑 | `MilestoneConstraint`、求解器里程碑匹配、`MilestonesTab.tsx`、结果展示 |
| 前端展示 | `frontend/src/app/App.tsx`、类型定义、标签、状态失效、移动端和宽屏可读性 |
| Netlify 演示 API | `netlify/functions/api.mts`，注意与 Python 后端能力差异 |
| 文档 | 目标 `docs/` 文件、相关代码事实、相关测试和交叉引用 |

## 12. 配置与安全

- `.local.env` 由 `backend/app/local_config.py` 启动时读取，禁止提交或写入真实值。
- Supabase 写入凭据只允许后端使用，浏览器端不应暴露。
- LLM / HTTP / OpenAI-compatible 适配器凭据只能通过 `.local.env` 或部署环境变量配置。
- README 和 `.local.env.example` 中只能使用占位符。
- 不提交 `.venv/`、`node_modules/`、`frontend/dist/`、`.local-data/`、日志、缓存和 `__pycache__/`。

常用环境变量：

- `SUPABASE_POSTGRES_SESSION_POOL_URL`
- `SUPABASE_POSTGRES_POOL_SIZE`
- `BRIDGE_IMPORT_LLM_PROVIDER`
- `BRIDGE_IMPORT_LLM_ENDPOINT`
- `BRIDGE_IMPORT_LLM_MODEL`
- `BRIDGE_IMPORT_LLM_API_KEY`
- `PROCESS_NL_LLM_PROVIDER`
- `PROCESS_NL_LLM_ENDPOINT`
- `PROCESS_NL_LLM_MODEL`
- `PROCESS_NL_LLM_API_KEY`
- `PROCESS_NL_LLM_TEMPERATURE`
- `PROCESS_NL_LLM_RESPONSE_FORMAT`

## 13. 协作和维护规则

- 编辑中文文档时保持 UTF-8。
- 修改前查看 git 状态，不覆盖无关改动。
- 文档输出要区分源码事实、需求文档口径、Demo 限制和工程目标。
- `docs/` 和 `skills/` 可能被忽略规则覆盖，但仍可能包含重要资产；读取和检查时使用显式路径。
- 业务逻辑变更优先补测试。
- 前端展示变更优先检查类型、状态失效和响应式可读性。
- 新增构件类型时，同步检查后端模型、前端标签、工艺库、逻辑本体、Netlify 演示 API 和测试。
- 删除或合并文档前，先检查是否存在引用；删除后更新相关引用。
- 不默认修改 README、`.gitignore`、提交 git 或推送远端，除非用户明确要求。

## 14. 需要用户确认的常见情形

遇到以下情形时，先向用户确认：

- 同一需求存在两个以上可行产品口径。
- 代码和需求文档冲突，且无法判断目标应以哪一方为准。
- 用户要求“优化”“调整”“完善”，但没有说明目标用户、验收口径或影响范围。
- 需要删除文档、迁移目录、调整共享模型字段或影响历史数据。
- 实现需要引入新依赖、改变部署方式或修改跨端接口契约。
- 算法规则会改变求解结果、里程碑判断、资源建议、连续性指标或方案对比。

确认问题应短而具体，优先问会改变方案方向的问题，不要求用户一次性补齐所有细节。
