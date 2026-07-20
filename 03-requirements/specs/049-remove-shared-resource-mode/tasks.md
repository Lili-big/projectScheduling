# 任务清单：移除资源共享模式

**输入**：`03-requirements/specs/049-remove-shared-resource-mode/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/project-resource-cleanup.md` 和 `quickstart.md`

**实施门禁**：用户确认本清单和下方一致性检查结果后，才能执行 `$speckit-implement`。

## Phase 1：用户故事 1 - 现有项目只保留工点资源（P1）

**目标**：清理默认及已有项目配置中的共享池，允许清理后资源集合为空，并完整保留工点独享资源。

**独立测试**：使用临时 JSON 加载显式共享、缺失作用域旧共享、直接本地池和 legacy 独享池，验证共享池被原子清除、合法本地池保真且重复加载幂等。

- [x] T001 [P] [US1] 在 `04-demo/backend/tests/test_local_scenario_config.py` 增加显式/默认共享池清理、legacy 独享池保留、仅共享项目变为空、原子写回失败和重复加载幂等测试
- [x] T002 [P] [US1] 在 `04-demo/backend/tests/test_architecture_api_contract.py` 增加 `LocalScenarioConfigSaveRequest.resource_pools=[]` 可解析且 PUT 响应允许空数组的契约测试
- [x] T003 [P] [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 将场景标准化预期改为删除共享池、保留工点池，并保留共享枚举/单池标准化底层兼容测试
- [x] T004 [US1] 在 `04-demo/backend/app/contracts/_models.py` 取消 `LocalScenarioConfigSaveRequest.resource_pools` 的 `min_length=1` 限制，同时保持字段必填和 `ResourcePool` 共享识别契约不变
- [x] T005 [US1] 在 `04-demo/backend/app/local_scenario_config.py` 将本地配置版本升级为 v4，先无损展开 legacy 独享池、再过滤 `PROJECT_SHARED`，允许空集合，并在本地加载发现共享记录时复用临时文件替换完成原子写回
- [x] T006 [P] [US1] 在 `04-demo/backend/app/scenario_data.py` 清空代码默认共享资源池，保持资源目录/工艺推导不通过默认池重新创建共享数据
- [x] T007 [P] [US1] 在 `04-demo/backend/app/default_scenario_config.json` 将 bundled `resource_pools` 清空，其他工艺、逻辑和里程碑数据保持不变
- [x] T008 [US1] 在 `04-demo/frontend/src/domain/resources.ts` 让 `normalizeScenarioResourcePools` 只返回工点独享池，并在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 保持共享池入口、说明和创建逻辑为 0

**检查点**：`GET /api/demo-scenario` 和 `PUT /api/local-scenario-config` 的当前资源集合只含工点独享池且允许为空。

---

## Phase 2：用户故事 2 - 项目计算不触发共享资源（P1）

**目标**：正常项目流程使用已清理的数据计算；不修改求解器处理显式共享输入的既有能力。

**独立测试**：仅共享项目经配置加载后生成任务，验证没有共享候选/实例/诊断且本地资源缺口阻断；随后运行现有显式共享求解测试证明底层能力仍通过。

- [x] T009 [US2] 在 `04-demo/backend/tests/scheduling/test_fixed_resource_application.py` 增加“项目配置清理后不触发共享计算”和“仅共享旧项目按本地资源缺口阻断”的贯通测试，不改写显式共享求解样例
- [x] T010 [P] [US2] 在 `04-demo/tools/demo-api-mirror/verify.mjs` 增加默认/缓存项目数据不得产生共享池、底层 `resourcePoolMatchesTask` 仍保留共享分支的静态契约检查
- [x] T011 [US2] 在 `04-demo/tools/demo-api-mirror/api.mts` 清空镜像默认共享池，并在本地缓存合并、保存响应和正常场景生成前只保留直接工点独享池，不删除底层共享匹配函数

**检查点**：正常项目计算的共享数据计数为 0，`test_workpoint_resource_scope.py` 的显式共享求解能力保持通过。

---

## Phase 3：用户故事 3 - 当前下游保持无共享语义（P2）

**目标**：页面、保存 payload、当前场景指纹和新生成结果不再传播共享池，历史保存结果不被追溯改写。

**独立测试**：从带旧共享池的项目进入生产 Workspace，验证页面无共享入口、保存 payload 无共享池、当前生成结果无共享身份，且测试中预置的历史结果对象保持不变。

- [x] T012 [US3] 在 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 将生产 Workspace 用例改为断言加载/保存 payload 中共享池为 0、共享编辑器不存在、当前生成结果不含共享身份，并验证历史结果对象未被清理流程追溯修改

**检查点**：正常前端流程不再恢复或传播共享资源，现有场景指纹失效机制覆盖清理后的集合变化。

---

## Phase 4：最小风险验证

**目标**：以不同证据覆盖迁移、公开契约、正常项目计算、底层共享能力保留、前端保存和参考镜像，不重复运行全仓库门禁。

- [x] T013 运行 `python -m pytest 04-demo/backend/tests/test_local_scenario_config.py 04-demo/backend/tests/test_architecture_api_contract.py 04-demo/backend/tests/scheduling/test_fixed_resource_application.py 04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py -q`，一次验证数据清理、空数组契约、正常项目不触发共享和底层共享能力仍保留
- [x] T014 运行 `node --test tests/resourceWorkpointScope.test.mjs`（工作目录 `04-demo/frontend`），一次验证前端标准化和页面静态契约
- [x] T015 运行 `node --test tests/resourceWorkpointRuntime.test.mjs`（工作目录 `04-demo/frontend`）；如首次出现明确浏览器沙箱权限错误，按执行环境规则只改为沙箱外重跑一次，不尝试多组浏览器参数
- [x] T016 [P] 运行 `node 04-demo/tools/demo-api-mirror/verify.mjs`，验证参考镜像类型和项目数据清理静态契约
- [x] T017 运行 `npm.cmd run typecheck` 和 `npm.cmd run build`（工作目录 `04-demo/frontend`），验证共享字段兼容类型与生产构建
- [x] T018 运行 `python 00-governance/repository-tools/validate_docs.py` 和针对 049/目标源码的 `git diff --check`，记录退出码、通过项和未覆盖风险后停止

---

## 依赖与执行顺序

- T001～T003 先建立失败/缺失证据，可在不同测试文件并行。
- T004 是空配置契约基础；T005 依赖 T001、T002、T004。
- T006、T007 可并行，但必须与 T005 一起完成后才能进入 US2。
- T008 依赖 T003；它与后端 T004～T007 不写相同文件，可并行实施。
- T009 依赖 T005～T007；T010 先于 T011，确保镜像变更有契约保护。
- T012 依赖 T008 和正常保存链路完成。
- T013～T018 只在全部实现任务完成后各运行一次；T016 与不写相同输出的验证可并行，T018 最后收口。

## 一致性覆盖矩阵

| 规格项 | 任务证据 |
|---|---|
| FR-001、SC-001 | T003、T008、T012、T014～T015 |
| FR-002～FR-005、FR-015、SC-002、SC-007 | T001～T008、T013～T014 |
| FR-006～FR-009、SC-003～SC-004 | T009、T011～T013、T015～T016 |
| FR-010～FR-012、SC-005 | T008、T012、T014～T015、T017 |
| FR-013、SC-006 | T012、T015 |
| FR-014 | T002～T004、T009～T011、T013、T016～T017 |
| FR-016 | T001～T003、T009～T012、T013～T018 |
| 数据清理失败与原子性 | T001、T005、T013 |
| 不修改求解器共享能力 | T009、T013；实施路径不包含 `scheduling/domain/resource_scope.py` 或 `scheduling/solver/` |

## 一致性检查结果

- 16 条 FR、7 条 SC、3 个用户故事和 6 项研究决策均已映射到至少一个实施或验证任务。
- 所有任务路径均位于 `plan.md` 收敛的 049 规格或 `04-demo` 实施范围内。
- 没有删除共享契约或修改求解器的任务；与用户最新确认一致。
- 仅安排一组定向后端测试、一次前端领域测试、一次浏览器运行时、一次镜像验证和一次类型/构建验证；没有重复全量测试。
- 当前无覆盖缺口、术语冲突、未解析依赖或实施阻塞。

## 2026-07-19 实施与验证记录

- T013 首轮为 34 项通过、1 项失败；失败原因是测试辅助函数遗漏传递 `enabled=enabled`。完成最小修正后只重跑受影响的参数化用例，4 项全部通过；没有修改生产诊断语义。
- T014：8 项前端领域与页面静态测试全部通过。
- T015：浏览器在任何页面断言执行前发生 `Page.enable` CDP 握手 60 秒超时。该结果分类为环境性非阻断失败，未更换多组浏览器参数或深挖运行环境；页面静态契约、请求标准化、类型检查和生产构建由 T014、T016、T017 覆盖。
- T016 首轮暴露验证脚本把 `04-demo/` 误认作仓库根目录；修正 `repoRoot` 后通过，输出 `demo API mirror: typecheck OK; deployment wiring absent`。
- T017：`npm.cmd run typecheck` 与 `npm.cmd run build` 均退出码 0，Vite 完成 1660 个模块的生产构建；仅保留既有大 chunk 警告。
- 已通过应用正常加载迁移将 `.local-data/state/scheduler-config.json` 从 v1 写回 v4：8 个共享池清除为 0，原项目没有工点独享池，未创建替代资源，临时文件已移除。
- T018：`validate_docs.py` 退出码 0，输出 `documentation links and API facts: OK (14 documents)`；049、目标源码及本轮实施契约的 `git diff --check` 退出码 0，仅有 Git 的 LF/CRLF 工作区提示。
