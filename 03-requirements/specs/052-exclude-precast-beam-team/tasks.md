# 任务清单：工点资源排除预制梁班组

**输入**：`03-requirements/specs/052-exclude-precast-beam-team/` 下的规格、计划、研究、数据模型和 UI 契约

**实施门禁**：本清单及一致性检查须由用户确认后才能执行 `$speckit-implement`。

## Phase 1：用户故事 1 - 工点资源不再出现预制梁班组（优先级：P1）

**目标**：从自动结构匹配和完整补充目录中同时排除 `precast_beam_team`，其他资源规则不变。

**独立测试**：包含预制梁、桩基、承台和架梁工艺的固定夹具中，目录及建议均不含 `precast_beam_team`，未排除资源继续存在。

- [x] T001 [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加排除契约测试：工艺目录即使包含 `precast_beam_team` 也不输出该项，预制梁构件不产生该建议，`rotary_drill`、`cap_team` 和 `beam_erection_team` 等未排除类型保持可用
- [x] T002 [US1] 在 `04-demo/frontend/src/domain/constants.ts` 将 `precast_beam_team` 加入现有 `excludedResourceCatalogTypes`，保留预制梁工艺映射、中文兼容名称和 `beam_erection_team`

**检查点**：工点资源页无法自动得到或手工补充预制梁班组，其他资源不回归。

---

## Phase 2：收敛验证

- [x] T003 运行 `node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs`，修正本变更导致的目录、结构匹配或既有资源回归失败并记录结果
- [x] T004 依次运行 `npm.cmd run typecheck` 和 `npm.cmd run build`，修正本变更导致的类型或构建失败并记录结果
- [x] T005 运行 `python 00-governance/repository-tools/validate_docs.py`，修正 052 规格资产相关失败并记录结果

## 依赖与执行顺序

- T001 → T002：先固定失败/缺失的资源排除契约，再修改统一排除集合。
- T003–T005 在实现后顺序执行；本功能不需要浏览器运行时、后端测试或全量门禁。
- 只有两个代码/测试文件且存在直接依赖，无并行任务。

## 一致性检查

- **用户故事验收 1–3 / FR-001–FR-005 / SC-001–SC-003**：T001–T003。
- **FR-006**：T002 的最小常量变更及任务路径边界明确保证不修改梁场、任务、后端或求解器。
- **FR-007 / SC-004**：T001、T003–T005。
- 计划的统一排除集合决策由 T002 实现；历史数据保留和架梁班组不受影响由 T001 回归断言保护。
- 无未覆盖需求、冲突术语、越界路径、重复验证或缺失依赖。

**检查结果**：通过，可以进入用户确认门禁。

## 实施与验证记录

**实施日期**：2026-07-20

- T001–T002：仅修改 `excludedResourceCatalogTypes` 和邻近领域测试；未修改页面组件、预制梁工艺、后端、梁场或求解器。
- T003：`node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 退出码 0，12/12 通过；已证明目录与结构建议排除 `precast_beam_team`，并保留旋挖钻机、承台模板和架梁班组。
- T004：`npm.cmd run typecheck` 与 `npm.cmd run build` 均退出码 0；构建仅有既有的 chunk 大于 500 kB 警告。
- T005：`python 00-governance/repository-tools/validate_docs.py` 退出码 0，输出 `documentation links and API facts: OK (14 documents)`。
- Spec Kit 共享指针在实施时已被其他工作项切换到 053；为保护并行工作未覆盖该指针，直接核验并执行用户确认的 052 `plan.md`/`tasks.md`。

**完成判定**：5/5 任务完成，核心验收和回归边界均有通过证据，无未覆盖的功能风险。
