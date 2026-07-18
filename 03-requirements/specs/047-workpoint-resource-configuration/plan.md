# 实施计划：工点级资源配置

**分支/目录**：`047-workpoint-resource-configuration` | **日期**：2026-07-17 | **规格**：`03-requirements/specs/047-workpoint-resource-configuration/spec.md`

**输入**：来自当前功能目录 `spec.md`、既有资源配置 PRD v1.3 和独立资源规则 v1.0。

## 概要

在现有项目级 `ResourcePool` 上增加通用工点作用域和覆盖，标准化为项目共享池或工点独享池后再生成显式命名资源。任务候选同时按资源类型和 `bridge_id` 工点范围筛选；求解器继续复用命名资源互斥/容量约束。三类数量语义固定为：固定资源用 `quantity`、增配建议搜索 `[quantity,max_quantity]`、固定工期最少资源的下界不受 `quantity` 限制。页面、AI 助手、持久化、指纹和结果诊断贯通同一模型。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript 5；项目发布基线 Node.js 22

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite；不新增依赖

**存储**：`.local-data/state` JSON 本地配置与现有计划管控仓储；沿用现有标准序列化、稳定指纹和快照

**测试**：pytest、Node `--test`、前端 typecheck/Vite build、真实组件行为测试、根级 `verify:architecture`

**目标平台**：本地 FastAPI + Vite 工作台及现有 Netlify 构建链

**项目类型**：跨前后端 Web 应用、资源模型和 CP-SAT 求解联动

**性能目标**：资源配置标准化和候选筛选在现有典型 1586 任务规模下不成为求解主耗时；保持既有单次求解时间预算，不因页面展示产生 N×W 串行请求

**约束**：不新增 `min_quantity`；不解析名称/ID 判断作用域；不修改工艺映射、目标函数或既有专项规则；项目共享转场固定 0 天；不进入非桥梁工点

**规模/范围**：共享契约、任务生成、资源候选、求解、AI 资源助手、本地/计划快照持久化、资源页、结果提示和自动化回归

## 生命周期归属

- **主要阶段**：`03-requirements`
- **工作包**：`047-workpoint-resource-configuration`
- **资产类型**：Spec Kit 正式成果
- **跟踪策略**：`tracked`
- **保留类别**：`formal-output`
- **主归属**：`03-requirements/specs/047-workpoint-resource-configuration/`
- **跨阶段引用**：实现和测试仍归 `04-demo/`；本目录只定义契约、任务图和验收，不复制代码。

## Constitution 检查

### Phase 0 前

- [x] L02 已完成产品决策，G00 已路由到 L03 正式规格化。
- [x] `spec.md` 已引用来源文档和真实 Demo/代码事实。
- [x] 资源、CP-SAT、前后端共享字段、AI 和持久化影响已明确。
- [x] 输入、输出、硬约束、数量边界、异常和验收样例可测试。
- [x] 项目共享转场 0 天被标为 MVP 限制，不提升为长期真实转场模型。
- [x] 全部 Spec Kit 文档使用简体中文。
- [x] 已声明资产归属；不迁移现有资产，不修改 README。

### Phase 1 后

- [x] 数据模型只扩展现有 `ResourcePool/Resource`，没有平行权威资源模型。
- [x] API 契约复用现有保存、生成、求解和 AI 端点。
- [x] 兼容默认、集合标准化和指纹规则已明确。
- [x] 候选只读显式字段，不解析命名资源 ID。
- [x] 每个实现领域和独立复核职责可由 G00 按注册表路由。
- [x] 没有宪章违反项。

## 项目结构

### 本功能文档

```text
03-requirements/specs/047-workpoint-resource-configuration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-scope.openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 预期实施位置

```text
04-demo/backend/app/contracts/                  # 共享模型
04-demo/backend/app/scheduling/                 # 标准化、生成、候选和求解
04-demo/backend/app/local_scenario_config.py    # 本地配置兼容迁移
04-demo/backend/app/services/                   # AI 助手、计划快照与失效
04-demo/backend/app/api/                        # 现有端点契约复核
04-demo/frontend/src/contracts/                 # 前端共享类型
04-demo/frontend/src/domain/resources.ts        # 通用资源标准化
04-demo/frontend/src/features/resources/        # 配置页
04-demo/frontend/src/features/resourceAssistant/# AI 方案页面
04-demo/frontend/src/features/scheduleResults/  # 结果提示
04-demo/frontend/src/app/Workspace.tsx           # 状态、失效和工作台接入
04-demo/backend/tests/                          # 后端/契约/兼容回归
04-demo/frontend/tests/                         # 前端行为与构建回归
```

**结构决策**：以现有共享契约为单一模型，D02 负责排程核心，D05 负责工作台体验，D07 负责 AI 助手，D04 负责计划快照/失效，D06 负责共享契约与独立门禁；L03 只维护规格和任务图，由 G00 统一派发。

## 实施阶段

### Phase 0：研究与口径冻结

完成 `research.md` 中模型、继承、候选、数量、迁移、AI 和持久化决策；不得在实现阶段重新解释业务口径。

### Phase 1：契约与基础模型

先由共享契约定义 `scope_mode`、获准工点、工点覆盖和命名资源显式作用域；建立兼容反序列化、标准化和契约测试，再允许各领域接入。

### Phase 2：排程核心

在场景生成阶段解析有效共享/独享池，按固定/最大资源模式展开实例；求解候选按类型+工点筛选，保留既有互斥、同结构绑定、墩组和目标函数。

### Phase 3：持久化与 AI

本地配置、计划快照、指纹和 AI 方案保留新字段；AI 不可改变作用域，只能对既有有效池建议数量。

### Phase 4：页面与结果

资源页展示模式、权威工点、继承/覆盖、错误和版本隔离；结果页展示作用域、分配工点及转场 0 天提示；任何语义修改使旧输出失效。

### Phase 5：集成与独立复核

使用 quickstart 固定样例覆盖正常、异常、空态、迁移、AI、版本切换和三类求解；执行全量测试、构建、架构和硬编码扫描。

## 复杂度跟踪

无 Constitution 违反项。新增嵌套覆盖对象是表达“全局默认 + 工点覆盖”的最小结构；单独复制每个工点的完整资源池会产生多份权威值，已拒绝。
