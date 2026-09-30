# 实施计划：路面班制工效（单/双班区间）

**分支/目录**：`076-pavement-shift-productivity` | **日期**：2026-09-29 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `SPECIFY_FEATURE_DIRECTORY/spec.md` 的功能规格

## 概要

在路面排程中引入项目级班制区间（单班/双班），双班日产出为基准工效 ×2。核心改造是把"任务工期 = 常量"改为"任务工期 = 开始日期的确定性函数"（spec FR-003 公式），并在贪心构造、CP-SAT 建模、逐解独立复核三处共用同一函数；任务不拆分，`Task.duration_days` 保留为单班基准工期（同时是 horizon 上界与预览口径）。班制配置随 `ScheduleInput` 进入指纹，旧结果自动失效。未配置时全链路退化为现状行为（spec FR-005）。

## 技术上下文

**语言/版本**：Python 3.14（仓库 `.venv`，ortools 9.15.6755）；前端 TypeScript（Vite + React 18）

**主要依赖**：FastAPI、Pydantic v2、OR-Tools CP-SAT（已验证 `AddAllowedAssignments` 可用）、React

**存储**：无新增持久化；班制配置随路面设置走既有本地场景配置链路（`.local-data/state/scheduler-config.json` 合并顺序不变）

**测试**：pytest（`04-demo/backend/tests/`）+ 前端 Node 测试（`04-demo/frontend/tests/*.test.mjs`）+ `npm run typecheck`/`build`

**目标平台**：本地 FastAPI 服务 + Netlify 静态前端；`04-demo/tools/demo-api-mirror/api.mts` 参考镜像需同步 schema

**项目类型**：Web 应用（前后端联动 + 排程算法）

**性能目标**：19 段 76 任务量级、15 秒预算下求解耗时与结果质量与现状同量级（spec SC-004）

**约束**：不改变求解目标（最早施工完成）与既有硬约束语义；不改 CP-SAT seed/worker/时间预算机制；不拆任务；养生/间歇按自然天、转场天数不变（spec FR-006）；无配置时与现状逐位一致

**规模/范围**：后端契约 2 处、领域纯函数 1 个新模块、生成/求解策略/启发式 3 处改造、前端契约+LogicTab 编辑器+结果展示 3 处；测试新增约 6 个后端文件片段与 3 个前端测试文件片段；架构基线 2 个 fixture 重新捕获

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：
  - `04-demo/backend/app/contracts/pavement.py`（`PavementShiftRegime`、`PavementSettings.shift_regimes`）
  - `04-demo/backend/app/contracts/_models.py`（`ScheduleInput.shift_regimes`）
  - `04-demo/backend/app/scheduling/domain/shift_regime.py`（新增，工期函数唯一权威）
  - `04-demo/backend/app/scheduling/generation/pavement.py`（配置校验与快照）
  - `04-demo/backend/app/scheduling/solver/strategies/pavement.py`（建模变量工期、结果拆分）
  - `04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`（构造与复核用函数工期）
  - `04-demo/frontend/src/contracts/scheduler.ts`、`src/domain/pavement.ts`、`src/features/logic/LogicTab.tsx`、`src/features/scheduleResults/`、`src/app/Workspace.tsx`
  - 测试：`04-demo/backend/tests/test_pavement_*.py`、`04-demo/frontend/tests/pavement*.test.mjs`
  - 基线：`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`；`04-demo/tools/demo-api-mirror/api.mts`

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- 已完成需求评审，或已明确属于小范围变更无需评审。✅（spec 声明小范围变更；三项设计决策用户已确认）
- `spec.md` 已引用来源文档、Demo 事实和代码事实。✅
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。✅（本计划技术上下文与 Phase 1 产物落实）
- 输入、输出、约束、边界场景和验收标准可测试。✅（SC-001 数值样例 + FR-005 逐位一致）
- 未经明确批准，不把 Demo 临时限制提升为正式产品目标。✅（仅路面首版、1|2 班制均写在默认假设）
- `spec.md` 已声明唯一生命周期归属，本计划不复制第二份分类。✅
- 资产迁移具有逐项清单、清单外保护、引用更新和回退边界。✅（无资产迁移，仅代码与基线更新）
- 本地状态、用户输入和正式成果不会被当作缓存或临时文件清理。✅

**Phase 1 设计后复查**：✅ 通过——变量工期采用"每任务预计算工期表 + `AddAllowedAssignments`"，不新增求解目标、不改 `AddCircuit` 机组路径语义；逐解独立复核原则保留（FR-004）；无配置退化路径与既有实现逐位共享代码路径（同一函数在空班制下返回 `duration_days`），不产生第二套实现。

## 项目结构

### 本功能文档

```text
03-requirements/specs/076-pavement-shift-productivity/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出（契约变更清单）
│   └── backend-frontend-contract-changes.md
└── tasks.md             # Phase 2 输出（由 /speckit-tasks 创建）
```

### 生命周期与源码结构（仓库根目录）

```text
00-governance/                # 架构基线与治理门禁（不修改）
03-requirements/specs/076-pavement-shift-productivity/   # 本功能规格与设计
04-demo/backend/app/          # 契约、领域函数、生成、求解策略改造
04-demo/backend/tests/        # 后端测试与架构基线 fixture
04-demo/frontend/src/         # 契约类型、LogicTab 编辑器、结果展示
04-demo/frontend/tests/       # 前端 Node 测试与架构基线 fixture
04-demo/tools/demo-api-mirror/# Netlify 参考镜像 schema 同步
```

**结构决策**：工期函数放 `scheduling/domain/`（生成与求解共同依赖的纯函数层），不放进 contracts（契约不含行为）也不复制进 solver（避免第二定义）；`Task` 契约不加字段（`duration_days` 语义保持"单班基准工期"，拆分信息在结果层按需推导），避免动任务契约的宽影响面。

## 复杂度跟踪

> 无必须解释的 Constitution 违反项。
