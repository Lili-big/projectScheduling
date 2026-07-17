# 实施计划：项目架构治理与模块化升级

**分支/目录**：`042-repo-architecture-modernization` | **日期**：2026-07-16 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/042-repo-architecture-modernization/spec.md` 的功能规格

## 概要

本功能以行为保持型重构解决当前项目的三类结构性问题：后端入口、契约、场景编排和求解器集中在超大文件；前端工作台、共享类型、API 和样式缺少稳定业务边界；仓库入口文档、辅助工具、历史资料、交付物和本地产物的分类不清。

技术方向采用“模块化单体 + 兼容门面 + 分批迁移”：先固化 OpenAPI、共享契约、固定场景不变量、前端失效规则和当前测试基线；再建立新模块边界，保留旧导入路径和运行入口作为兼容层；每批只迁移一个职责集合，完成回归后再继续。`README.md`、`agent.md`、详细架构文档和资产索引在结构稳定后同步更新，但第一批会先修正明显失真的项目事实。

## 技术上下文

**语言/版本**：Python 3.12.13（Docker 目标 Python 3.12）；TypeScript 5.9.3；当前验证环境 Node.js 24.14.1、npm 11.11.0。生产兼容版本仍以 `Dockerfile`、`netlify.toml` 和前端依赖约束为准，本功能不主动升级版本。

**主要依赖**：FastAPI 0.136.3、Pydantic 2.13.4、OR-Tools 9.15.6755、openpyxl、pytest 9.0.3；React 19、Vite 6、lucide-react。首轮不新增运行时依赖、状态框架、CSS 框架或测试框架。

**存储**：继续使用代码内置默认配置、`.local-data/scheduler-config.json`、`.local-data/project-structure-params.json`、`.local-data/plan-control-store.json` 和本地上传/样例文件；不改变路径、schema、合并顺序和版本冲突语义。

**测试**：当前基线为后端 32 个测试文件，`328 passed, 1 skipped`；前端 3 个 Node 测试文件，21 个用例全部通过；`tsc && vite build` 通过。计划补充 OpenAPI 路由清单、Pydantic schema、兼容导入、固定场景不变量、前端 API/类型兼容、依赖方向和文档链接检查。

**目标平台**：Windows PowerShell 本地开发；FastAPI 单服务演示；Vite 前后端分离开发；Docker FastAPI 后端；Netlify 静态前端。`netlify/demo-functions` 当前仅为参考镜像，不是正式后端。

**项目类型**：桥梁施工排程模块化单体 Web 应用，包含前端、后端、算法、辅助工具、产品/研发文档、Spec Kit 规格和正式交付物。

**性能目标**：不降低现有排程和构建基线；继续满足 `041` 的 800 个综合任务、300 个架梁分跨性能门禁；同一环境下典型固定输入的重构后运行时间不比基线恶化超过 10%；前端主 JS/CSS 构建体积不因纯重构增长超过 5%。

**约束**：不改变 CP-SAT 目标、约束、阶段路由、随机种子、worker、时间预算、warm start、候选排序或诊断语义；不改变 45 个现有 `/api` 路由、共享字段、状态码、错误 `detail`、启动命令、静态托管、配置合并和 `041` 任务状态；不移动或删除用户本地未跟踪文件；正式交付物与历史规格必须保留可追溯性。

**规模/范围**：后端当前包含 45 个 API 路由、153 个 Pydantic 模型、`solver.py` 214 个顶层函数、`scenario.py` 128 个顶层函数；前端 `App.tsx` 4824 行、`types/scheduler.ts` 1901 行、`schedulerApi.ts` 40 个公开函数、`styles.css` 4927 行；仓库包含 567 个可见文件、315 个已跟踪规格文件、27 个 `docs/` 文件、70 个已跟踪 PPT 辅助工具文件和 20 个已跟踪 `outputs/` 文件。

## Constitution 检查

*门禁：Phase 0 研究前已检查；Phase 1 设计后再次检查。*

- [x] 用户明确要求实施架构重构和文档升级；该中大型跨模块变更已进入完整 Spec Kit，而非直接改代码。
- [x] `spec.md` 已引用 `AGENTS.md`、`agent.md`、`README.md`、Constitution、当前代码、测试和 `041` 事实。
- [x] 本功能不改变排程、资源、工期和 CP-SAT 业务语义；可能影响的 API、共享契约、配置、静态托管和结果不变量已列为兼容门禁。
- [x] 输入、输出、模块边界、资产分类、迁移批次、失败场景和成功标准均可验证。
- [x] 未把 Demo、Netlify 参考镜像、本地产物或 `041` 规格目标提升为正式已实现能力。
- [x] 所有 Spec Kit 产物使用中文简体，代码标识符、路径、命令和任务编号保持原文。
- [x] 设计阶段未引入新框架、新运行时依赖、微服务、数据库迁移或部署平台变更。
- [x] Phase 1 复核结论：所有 MUST 级门禁继续满足，无需复杂度豁免。

## 项目结构

### 本功能文档

```text
specs/042-repo-architecture-modernization/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── architecture-compatibility-contract.md
│   └── repository-layout-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 目标源码与资产结构（仓库根目录）

```text
.
├── README.md                         # 首次使用、快速启动、验证、部署和导航
├── AGENTS.md                         # 工作流与治理门禁
├── agent.md                          # 当前事实、模块所有权、调用链和修改矩阵
├── .local-data/                      # 本地忽略数据；logs/ 为唯一落盘日志目录
├── backend/
│   ├── app/
│   │   ├── main.py                   # 保留 uvicorn 兼容入口
│   │   ├── bootstrap.py              # app factory、CORS、依赖装配、静态托管
│   │   ├── api/routers/              # system、scenario、assistants、project、girder、plan_control
│   │   ├── contracts/                # common、project、scheduling、assistants、girder、plan_control
│   │   ├── scheduling/
│   │   │   ├── application/          # 场景求解、比较、资源搜索用例
│   │   │   ├── generation/           # 任务和结构派生
│   │   │   └── solver/               # strategies、constraints、objectives、results、diagnostics
│   │   ├── girder_planning/           # 架梁领域、适配和联合计算入口
│   │   ├── plan_control/              # 计划版本、实绩、预测与仓储入口
│   │   ├── assistants/                # 参数与资源助手
│   │   ├── importing/                 # 桥梁和实绩导入
│   │   ├── config/                    # 环境、本地配置、发布默认配置
│   │   ├── models.py                  # 旧契约兼容重导出
│   │   ├── scenario.py                # 旧场景入口兼容转发
│   │   └── solver.py                  # 旧求解入口兼容转发
│   └── tests/                          # 按业务域组织，保留全量回归
├── frontend/
│   ├── src/
│   │   ├── app/                       # 工作台装配、跨功能协调、全局错误
│   │   ├── api/                       # client + 按业务域 API 适配
│   │   ├── contracts/                 # 按业务域拆分共享 DTO
│   │   ├── domain/                    # 无 React、无网络的共享纯规则
│   │   ├── features/                  # 业务纵切，统一通过 index.ts 暴露
│   │   ├── components/common/
│   │   ├── styles/                    # tokens、base、layout；功能样式与 feature 共置
│   │   ├── types/scheduler.ts         # 旧类型入口兼容重导出
│   │   ├── api/schedulerApi.ts        # 旧 API 入口兼容重导出
│   │   └── App.tsx                    # 默认导出兼容入口
│   └── tests/
├── docs/
│   ├── README.md                      # 文档索引、状态、权威性和维护触发条件
│   ├── architecture/                  # 上下文、模块地图、依赖规则、运行部署、ADR
│   ├── product/                       # 产品目标、整体方案和 PRD
│   ├── engineering/                   # 算法交底、接口和工程说明
│   ├── validation/                    # 验证说明与验收记录
│   ├── research/                      # 客户调研材料
│   └── archive/                       # 已替代资料与迁移映射
├── specs/
│   └── README.md                      # 规格索引；历史目录不移动、不重编号
├── examples/                          # 桥梁导入样例、结果查看器和精简结果
├── tools/                             # ai-ppt-system、参考 API、交付物生成器
├── deliverables/                      # 经确认需版本控制的正式交付件
└── artifacts/                         # 本地生成、预览和检查中间件，默认忽略
```

**结构决策**：选择模块化单体，不拆微服务。后端依赖方向为 `api -> application -> domain`，基础设施在 `bootstrap` 装配；跨业务域只调用公开 application façade。前端依赖方向为 `app -> features -> domain/api/contracts/common`，禁止 `domain` 反向依赖 UI/网络，也禁止 feature 导入另一 feature 的内部文件。旧入口在本功能内保留为兼容门面，不安排删除。

## 迁移批次

### Batch 0：基线与治理门禁

- 生成当前 OpenAPI 路由清单、代表性 Pydantic schema、Python/TypeScript 旧导入清单、Python/npm 运行时依赖清单和固定场景业务不变量。
- 拆分测试组织但不改变测试语义；增加真实 HTTP、兼容入口、架构依赖和文档链接检查。
- 记录当前性能、前端包体、仓库资产清单、正式二进制哈希和 `041` 未完成状态。
- 在任何生产文件迁移前建立每个 Batch 的前置条件、验证证据、回退步骤和阻断状态模板；每个 Batch 完成时即时回填，不在末尾追记。

### Batch 1：入口文档与资产治理设计

- 先修正 `README.md`、`agent.md` 中错误 API、模块、Netlify 路径和当前能力描述。
- 新增 `docs/README.md`、`docs/architecture/`、`specs/README.md` 和资产迁移表。
- 本批只建立资产分类、目标路径、引用、哈希和回退清单，不执行 `git mv`、取消跟踪或正式交付物分区。
- 将根目录本地 `*.log` 逐文件加入清单，目标为 `.local-data/logs/legacy/`；先建立统一后台日志入口，未获二次确认前不移动或删除历史日志。
- 样例 Excel 在兼容搜索路径、Docker 复制和回归测试完成前暂留根目录。

### Batch 2：后端启动与 HTTP 边界

- 引入 `bootstrap.py` 和按业务域 routers；`main.py` 只保留兼容 app/endpoint 入口。
- 统一 HTTP 异常映射，但不改变状态码和 `detail`。
- 使用 OpenAPI manifest 与 `TestClient` 验证 45 个现有路由、静态资源和 SPA 回退。

### Batch 3：后端共享契约与业务所有权

- 按域拆分 `contracts/`，`app.models` 完整重导出；先迁移消费者，再压缩兼容文件。
- 将架梁联算、计划管控、AI 助手、导入能力从泛化 `services/` 收拢到对应业务包，旧路径保留转发。
- 将环境加载、本地场景配置、工艺配置仓储和发布默认配置访问收拢到 `config/`，保持原配置文件路径、schema、合并顺序和旧导入入口。
- 验证 JSON schema、`model_dump(mode="json")`、本地存储 schema、稳定 ID/指纹和错误语义。

### Batch 4：场景与求解器拆分

- 先迁移纯工具、诊断和结果转换，再迁移约束、目标和模型构造，最后迁移求解策略与场景应用编排。
- `scenario.py`、`solver.py` 继续作为兼容 façade；禁止复制规则形成双实现。
- 每一小批使用固定输入比较任务日期、资源分配、里程碑、目标分解、诊断、来源标签和候选排序。

### Batch 5：前端兼容端口与工作台拆分

- 新增按域 contracts/API，保留 `types/scheduler.ts` 和 `schedulerApi.ts` 重导出。
- 依次迁移 `DateRangePicker`、任务视图、结果视图、诊断 presenter、求解 workflow/controller；`App.tsx` 最终只装配工作台。
- 收拢 `PlanControlPanel` 和跨 feature 依赖；通过公开 `index.ts` 或 app 组合连接。
- 在组件所有权稳定后迁移 CSS，保持选择器和导入顺序，最后压缩全局样式入口。

### Batch 6：文档收敛与最终治理

- 提交逐文件资产迁移清单，必须获得用户二次明确确认后，才对确认项执行 `git mv`、取消跟踪、正式交付物分区、根目录日志本地移动和样例数据迁移；历史规格不移动，未确认项保持原状。
- 用真实模块、API、配置、命令和测试结果完成 `README.md`、`agent.md`、架构文档、文档/规格/交付物索引。
- 对迁移后的 PPT 工具执行本地类型/布局校验，对参考 API 执行无部署语法/类型检查，对交付物构建器执行固定夹具构建与复核；目录迁移本身不能替代可运行验证。
- 执行全量引用、仓库卫生、包体、模块体积、依赖方向、OpenAPI、行为基线、单服务健康和人工浏览器旅程检查。
- 保留兼容门面和迁移表；移除兼容层属于未来独立破坏性版本，不在本功能内。

## 复杂度跟踪

无 Constitution 违反项。模块数量增加是对现有 45 个路由、153 个契约模型、342 个场景/求解函数和 202 个前端导出类型的职责拆分，不引入新的业务层级、运行进程或部署单元。

## Agent 上下文更新说明

仓库当前不存在 `$speckit-plan` 所期望的 `.specify/scripts/powershell/update-agent-context.ps1`，因此设计阶段未执行自动 Agent 上下文写入。`agent.md` 的真实更新已纳入 Batch 1 和 Batch 6，必须在用户确认任务并进入实施后完成；本阶段不绕过实现门禁直接修改入口文档。
