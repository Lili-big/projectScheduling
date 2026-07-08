# 实施计划：精排目标指标前端全量展示与配置

**分支/目录**：`007-objective-metric-config` | **日期**：2026-07-06 | **规格**：`specs/007-objective-metric-config/spec.md`

**输入**：来自 `/specs/007-objective-metric-config/spec.md` 的功能规格

**说明**：本计划停留在 Spec Kit 门禁阶段。用户确认 `tasks.md` 与分析结果后，才能进入实现。

## 概要

本功能把精排后端实际参与目标函数的加权指标完整暴露到前端：求解前可查看和配置所有可配置目标项，求解后可看到每个目标项的原始罚分、有效权重和加权贡献。同时将连续性评分、跳跃、换向、普通工程均衡评分等只读诊断指标从目标项配置中分离，避免把解释性指标误当成可调目标。

技术处理方向：

- 后端建立目标指标目录和统一目标贡献输出。
- 后端仅将当前 4 个有效目标项纳入配置契约；放松目标诊断、`unconfigured_normal_balance`、槽位均衡诊断等只作为兼容或只读诊断展示，不恢复为可配置目标项。
- 前端目标函数配置表改为覆盖完整目录，并在结果页展示贡献表与诊断指标。
- 保持旧场景、旧请求和旧结果兼容。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、React。

**主要依赖**：FastAPI/Pydantic、OR-Tools CP-SAT、React/Vite。

**存储**：不新增持久化存储；继续使用现有本地场景配置和前端内存状态。

**测试**：后端 `pytest`，前端 TypeScript/Vite 构建；必要时补充针对目标配置和结果贡献的单元或集成测试。

**目标平台**：本地后端服务、React 前端、本地 Demo；Netlify 函数保持字段兼容。

**项目类型**：前后端联动、后端契约扩展、算法目标函数配置展示。

**性能目标**：新增指标目录和贡献计算不得显著增加 CP-SAT 建模复杂度；目标项拆分不得引入额外求解轮次。

**约束**：

- 不新增硬约束，不重写求解分支。
- 不把 Demo 临时口径写成正式产品规则。
- 不把只读诊断项提升为可配置目标项。
- 新增默认值必须保持旧场景求解行为等价。
- 用户未确认前不实施代码。

**规模/范围**：

- 后端：`backend/app/models.py`、`backend/app/solver.py`、必要时 `backend/app/scenario.py`、测试。
- 前端：`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`，必要时相关 API/派生展示工具。
- Netlify：`netlify/functions/` 仅做字段兼容。
- 文档：更新目标函数算法说明文档。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- 已明确该需求属于目标函数、排程指标和前后端契约联动，按 `AGENTS.md` 进入 Spec Kit。
- `spec.md` 已引用来源文档、Demo 事实和代码事实。
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。
- 输入、输出、约束、边界场景和验收标准可测试。
- 未把 Demo 临时限制提升为正式产品目标。
- Spec Kit 过程文档使用中文简体；代码标识符、文件路径、接口名、任务编号和必要英文缩写保持原文。

**Phase 0 结论**：通过。无 Constitution 违反项。

**Phase 1 复核**：通过。设计产物限定在现有后端模型、求解器、前端页面和兼容接口内，不引入新架构或新依赖。

## 项目结构

### 本功能文档

```text
specs/007-objective-metric-config/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── objective-metric-config-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py          # 目标项类型、默认配置、校验和输出模型
│   ├── solver.py          # CP-SAT 目标函数、目标贡献计算、诊断输出
│   └── scenario.py        # 场景求解编排和结果透传，按需调整
└── tests/                 # 后端目标配置和结果贡献测试

frontend/
└── src/
    ├── types/scheduler.ts # 共享类型
    └── app/App.tsx        # 目标配置 UI、结果贡献展示、状态失效

netlify/
└── functions/             # 演示接口字段兼容

docs/
└── 精排目标函数算法需求文档_v4.0.md # 实现阶段更新，版本号以最终文档为准
```

**结构决策**：不新增独立服务或新依赖。目标指标目录优先落在后端模型层，求解贡献在 `solver.py` 统一计算，前端只消费目录和结果贡献，不复制后端目标函数逻辑。

## 复杂度跟踪

无 Constitution 违反项，不需要复杂度豁免。
