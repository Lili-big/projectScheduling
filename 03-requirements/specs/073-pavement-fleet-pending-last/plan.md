# 实施计划：待移交段按单套机组后置

**目录**：`073-pavement-fleet-pending-last` | **日期**：2026-09-28 | **规格**：[spec.md](./spec.md)  
**分支**：沿用当前工作树；创建器未创建或切换 Git 分支。

## 概要

删除跨机组的正常段整体完成边界，复用每套实际资源实例的路径约束：正常任务在前、待移交任务在后。同步初解、数值校验和规则标识，结果及任务预览说明与其快照一致。用户确认后已实施，完成证据见 tasks.md。

## 技术上下文

- 语言/依赖：沿用当前 Python 虚拟环境、OR-Tools、Pydantic/FastAPI，以及 TypeScript 5.7、React 19、Vite 6；不升级依赖。
- 存储：无数据库迁移；只扩展现有范围元数据的规则枚举，既有历史 JSON 可读。
- 平台/类型：本地路面排程 Web 应用的后端约束及前端说明。
- 测试：pytest、Node 内置前端测试、前端构建、契约/架构基线校验及只读状态对比。
- 性能：沿用多线程、LNS 和既有预算，不新增重复两两排序约束。保持有限预算与持续返回合法最好方案。
- 规模：当前客户 19 段、95 道工序、共享机组与沥青机组；规则不限于该规模或资源类型。

## 生命周期归属与路径

沿用 [spec.md](./spec.md) 的阶段归属。权威实施路径：

- `04-demo/backend/app/scheduling/solver/strategies/pavement.py`：移除 normal_finish 约束及 hint；旧输入检查、新输出标识。
- `04-demo/backend/app/scheduling/solver/constraints/pavement.py`：复用/说明已有禁止待移交到正常的机组路径边。
- `04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`：初解取消全局时间下限，按资源路线校验顺序。
- `04-demo/backend/app/scheduling/generation/pavement.py`、`04-demo/backend/app/contracts/pavement.py`：新规则与诊断。
- `04-demo/frontend/src/contracts/pavement.ts`、`src/features/taskView/TaskViewWorkspace.tsx`、`src/features/scheduleResults/presenter.ts`、`src/features/scheduleResults/ScheduleResultsWorkspace.tsx`：兼容与说明；后三者均相对于 `04-demo/frontend/`。
- 后端既有 `test_pavement_solver.py`、`test_pavement_hybrid.py`、`test_pavement_generation.py`、`test_pavement_contracts.py`、`test_pavement_api.py`、`test_pavement_stream.py`；前端既有 `pavementResults.test.mjs`、`pavementTaskPreview.test.mjs`、`pavementLiveSolve.test.mjs`。
- 后端与前端 `tests/fixtures/architecture/*-baseline.json`：仅更新新枚举实际影响，保留无关工作树内容；`03-requirements/specs/README.md` 更新状态索引。
- `04-demo/tools/demo-api-mirror/api.mts` 已明确拒绝路面请求（422 / PAVEMENT_FEATURE_NOT_SUPPORTED）；不扩展镜像能力、不伪造新规则结果。

## 设计决策

1. CP-SAT 的 AddCircuit 路径已按单个资源构造，并禁止 pending → normal。保留此约束以及真实 FS/SS/FF/SF、日期、互斥和相邻转场，删除全局正常任务最大结束边界，不新增独立排序模型。
2. 初解构造继续以正常任务优先为启发式，但时间下限仅来自真实关系、日期和该机组路线；不得将全部正常任务结束日加到待移交任务。若拓扑使正常任务优先构造受阻，可尝试满足前置的待移交候选，进入待移交阶段的机组不再接收正常任务。无法构造初解时保留 CP-SAT 兜底，不能将启发式失败当作无解。
3. 数值校验逐实际路线检查状态转换；正常结束后可接待移交，待移交后不可接正常，不使用候选资源集合冒充实际分配。
4. 无资源配套任务保留已有关系与日期，不附加全局后置，不恢复产品入口。
5. 新标识为 `per_fleet_last`；`strict_last` 仅用于历史反序列化与展示，携带旧标识重新求解时返回现有 `MODEL_INVALID` + `PAVEMENT_INPUT_OUTDATED` 并提示重新生成。无范围元数据的直接输入按现行规则计算。
6. 不重写历史结果，不静默替换页面既有计划；新规则通过重新生成/求解生效。需移交日期仍是方案输出，不是已确认输入。

## Constitution 检查

Phase 0 前：用户业务口径明确，规格引用当前页面与源码；输入/输出、约束/目标和验收齐全，通过。

Phase 1 后：以新增枚举区分新旧语义；覆盖错误、历史、直接输入和流式路径；无依赖/目录重构/状态迁移，无宪章例外，通过。现有项目中未找到 `update-agent-context` 脚本（已按文件名搜索），不为本功能新造脚本或修改 agent.md；这是非核心工具步骤缺失，不影响规格和实现。

## 本功能文档与实施顺序

`spec.md` → `research.md` → `data-model.md`、`contracts/pending-policy.md`、`quickstart.md` → `tasks.md` → 用户确认 → 实施。

先完成算法、初解及其回归，再完成标识与显示闭环，最后执行一次相关验证批次。具体任务和覆盖映射见 tasks.md。

## 复杂度跟踪

无新增复杂度例外；复用已有路径和模型。
