# 任务：根目录生命周期工作区治理

**输入**：`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`

**测试要求**：本功能涉及根目录、运行代码、规格工具、Skill、本地状态和大批资产迁移，所有治理、路径、行为和清理安全测试均为必需。

## Phase 1：准备与冻结基线

**目标**：冻结当前 042 后工作树、并行 043、运行入口和本地资产，确保后续清单只处理明确范围。

- [X] T001 记录分支、工作树、端口、活动进程、根目录和当前功能指针到 `03-requirements/specs/045-lifecycle-workspace-governance/implementation-log.md`
- [X] T002 [P] 冻结受跟踪、未跟踪、忽略文件及 SHA-256/大小/状态到 `03-requirements/specs/045-lifecycle-workspace-governance/repository-baseline.json`
- [X] T003 [P] 冻结根 npm、后端、前端、Docker、Netlify、Spec Kit 和 Skill 发现入口到 `03-requirements/specs/045-lifecycle-workspace-governance/compatibility-baseline.md`
- [X] T004 [P] 登记 042/043、根 Excel、未跟踪 DOCX、用户 JSON、本地数据库和正式二进制保护对象到 `03-requirements/specs/045-lifecycle-workspace-governance/protected-assets.json`
- [X] T005 校验 Constitution 1.2.0、requirements checklist 和 contracts JSON，并记录到 `03-requirements/specs/045-lifecycle-workspace-governance/implementation-log.md`

---

## Phase 2：基础治理与失败优先测试

**目标**：先建立目标结构、工作包、迁移和清理的机器契约；未完成本阶段不得生成执行清单。

- [X] T006 [P] 为根允许项、七阶段顺序和禁止通用目录增加失败优先测试：`00-governance/repository-tools/tests/test_lifecycle_root_layout.py`
- [X] T007 [P] 为阶段 README 必填字段和两跳导航增加失败优先测试：`00-governance/repository-tools/tests/test_lifecycle_stage_contract.py`
- [X] T008 [P] 为工作包 Schema、唯一阶段、输入/脚本/成果、Git 跟踪策略和保留策略增加失败优先测试：`00-governance/repository-tools/tests/test_workpackage_contract.py`
- [X] T009 [P] 为任务阶段/工作包/资产类型/保留策略/主要所有者归类增加失败优先测试：`00-governance/repository-tools/tests/test_asset_placement.py`
- [X] T010 [P] 为七类本地产物、dry-run 和受保护资产增加失败优先测试：`00-governance/repository-tools/tests/test_cleanup_policy.py`
- [X] T011 [P] 为根 npm、Demo、Docker、Netlify、Spec Kit 和 Skill 双路径过渡增加契约测试：`00-governance/repository-tools/tests/test_path_compatibility.py`
- [X] T012 创建阶段定义、权威资产和默认流转规则：`00-governance/asset-policy/lifecycle-stages.json`
- [X] T013 创建根兼容入口、保留原因、业务所有者和移除条件：`00-governance/asset-policy/root-compatibility.json`
- [X] T014 创建七类清理规则和保护优先级：`00-governance/asset-policy/cleanup-policy.json`
- [X] T015 实现根 `specs` 与 `03-requirements/specs` 的 Spec Kit 双路径定位和旧活动指针映射：`.specify/scripts/powershell/`、`.agents/skills/speckit-*/SKILL.md`

**检查点**：治理测试应在目标目录和描述尚未完整时按预期失败，且不会移动或删除资产。

---

## Phase 3：逐资产迁移清单与二次确认

**目标**：把所有受跟踪和拟处理本地资产转成逐条可审计清单；用户未确认时硬停止。

- [X] T016 根据冻结基线生成逐资产迁移候选、引用和回退：`00-governance/repository-tools/build_lifecycle_migration_manifest.py`
- [X] T017 按 contracts Schema 生成完整机器清单并标记 `awaiting-approval`：`03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json`
- [X] T018 生成按治理/调研/方案/需求/Demo/验证/交付/本地产物汇总的人类可读清单：`03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.md`
- [X] T019 向用户提交完整迁移清单、清单外保护、日志/缓存候选和回退摘要，并把明确确认记录到 `03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json`

**硬门禁**：T019 未完成时，T020～T077 全部停止；不得创建目标文件副本、执行 `git mv`、移动本地文件或清理日志缓存。

---

## Phase 4：用户故事 1 - 按产品阶段理解整个仓库（优先级：P1）

**目标**：形成真实的七阶段根目录所有权，让核心资产而非索引实际进入对应阶段。

**独立测试**：从根目录在两次进入内定位调研、方案、需求、Demo、验证和交付工作，并确认每个资产只有一个主归属。

- [X] T020 [P] [US1] 为七阶段导航和唯一主归属补充迁移后测试：`00-governance/repository-tools/tests/test_lifecycle_navigation.py`
- [X] T021 [P] [US1] 创建七个阶段 README、进入/退出条件和工作包索引：`00-governance/README.md`、`01-discovery/README.md`、`02-solution-analysis/README.md`、`03-requirements/README.md`、`04-demo/README.md`、`05-validation/README.md`、`06-delivery/README.md`
- [X] T022 [US1] 按批准清单迁移架构、仓库治理和历史映射资产：`00-governance/architecture/`、`00-governance/repository-tools/`、`00-governance/history/`
- [X] T023 [US1] 按批准清单迁移调研资料和来源数据分析资产：`01-discovery/documents/`、`01-discovery/workpackages/`
- [X] T024 [US1] 按批准清单迁移长期目标、融合方案和 MVP 方案：`02-solution-analysis/proposals/`、`02-solution-analysis/decisions/`
- [X] T025 [US1] 按批准清单迁移页面需求、算法规则和需求模板：`03-requirements/product/`、`03-requirements/rules/`、`03-requirements/templates/`
- [X] T026 [US1] 按批准清单迁移完整规格树并保持编号/内容；并行 043 仅在清单单独批准时移动：`03-requirements/specs/`
- [X] T027 [US1] 按批准清单原子迁移后端、前端、样例和 Demo 工具，并同步切换根构建/部署临时兼容入口：`04-demo/backend/`、`04-demo/frontend/`、`04-demo/examples/`、`04-demo/tools/`、`package.json`、`Dockerfile`、`netlify.toml`
- [X] T028 [US1] 按批准清单迁移验证计划、报告和工作包资产：`05-validation/plans/`、`05-validation/reports/`、`05-validation/workpackages/`
- [X] T029 [US1] 按批准清单迁移正式交付、案例和演示材料：`06-delivery/deliverables/`、`06-delivery/case-studies/`、`06-delivery/presentations/`
- [X] T030 [US1] 重写根导航、最短路径和兼容入口说明：`README.md`

**检查点**：受跟踪业务资产已按阶段拥有唯一主路径；根目录不再以类型目录表达业务所有权。

---

## Phase 5：用户故事 2 - 独立理解和运行工作包（优先级：P1）

**目标**：让 JSON 展示、泸古调研/验证、AI 案例和 AI PPT 的输入、脚本、成果与保留策略形成闭环。

**独立测试**：随机选择 JSON 展示、泸古验证和 AI 案例工作包，在 60 秒内说明输入、命令、成果和清理边界。

- [X] T031 [P] [US2] 为工作包 README、JSON 描述、Git 跟踪/保留策略和文件引用增加契约测试：`00-governance/repository-tools/tests/test_workpackage_index.py`
- [X] T032 [P] [US2] 建立通用 JSON 任务展示工作包并提升可复用脚本：`04-demo/standalone/json-task-viewer/`
- [X] T033 [P] [US2] 建立固定排程结果离线查看器工作包和批准样例：`04-demo/standalone/schedule-result-viewer/`
- [X] T034 [P] [US2] 建立真实 JSON 工程结果评审工作包并区分本地输入/结果：`05-validation/workpackages/json-schedule-review/`
- [X] T035 [P] [US2] 建立泸古客户调研与报告生成工作包：`01-discovery/workpackages/lugu-customer-research/`
- [X] T036 [P] [US2] 建立泸古来源工作簿结构分析工作包：`01-discovery/workpackages/lugu-source-data-analysis/`
- [X] T037 [P] [US2] 建立泸古验证工作簿构建和校验工作包：`05-validation/workpackages/lugu-validation-material/`
- [X] T038 [P] [US2] 建立泸古计划粒度比较和报告生成工作包：`05-validation/workpackages/lugu-plan-granularity/`
- [X] T039 [P] [US2] 建立 AI 案例总结工作包并登记来源/草稿/当前成果/历史版本：`06-delivery/workpackages/ai-case-summary/`
- [X] T040 [US2] 对无法确认生成脚本的 AI 案例成果标记 `orphaned` 并补充关联说明：`06-delivery/workpackages/ai-case-summary/workpackage.json`
- [X] T041 [P] [US2] 迁移 AI PPT 工具并修正输入、模板和输出路径：`06-delivery/presentations/ai-ppt-system/`
- [X] T042 [US2] 生成全仓库工作包索引和关系图，并记录三个抽样工作包的 60 秒计时验收：`00-governance/asset-policy/workpackages.json`、`00-governance/README.md`、`03-requirements/specs/045-lifecycle-workspace-governance/workpackage-walkthrough.md`

**检查点**：每个独立工作包可单独理解和运行；脚本、批准成果和本地产物之间无隐式路径。

---

## Phase 6：用户故事 3 - 后续任务自动选择归属（优先级：P1）

**目标**：把本次结构变成持续生效的 Agent 契约和自动校验，而不是一次性整理。

**独立测试**：六类模拟新任务全部命中唯一阶段、工作包、资产类型和保留策略；错误放置稳定失败。

- [X] T043 [P] [US3] 为六类模拟任务、跨阶段引用和未知工作包增加归类测试：`00-governance/repository-tools/tests/test_task_classification.py`
- [X] T044 [P] [US3] 创建资产放置决策树和机器规则：`00-governance/asset-policy/placement-rules.json`
- [X] T045 [P] [US3] 创建新工作包模板和必填描述：`00-governance/asset-policy/templates/workpackage/README.md`、`00-governance/asset-policy/templates/workpackage/workpackage.json`
- [X] T046 [US3] 更新工作分流，要求任务开始前声明五项归属：`AGENTS.md`
- [X] T047 [US3] 更新项目事实、生命周期所有权、取证顺序和修改矩阵：`agent.md`
- [X] T048 [P] [US3] 更新 Spec Kit spec/plan/tasks/checklist/constitution 模板的阶段和工作包字段：`.specify/templates/`
- [X] T049 [P] [US3] 更新项目 Skill 目录、阶段所有权和维护说明：`.agents/skills/README.md`、`00-governance/asset-policy/skill-catalog.json`
- [X] T050 [US3] 实现仓库治理入口，拒绝错误根目录、孤立脚本和未知生成物：`00-governance/repository-tools/validate_lifecycle_workspace.py`
- [X] T051 [US3] 更新根 README 的新增任务放置流程和快速决策表：`README.md`

**检查点**：后续任务不依赖人工记忆即可落入正确阶段和工作包。

---

## Phase 7：用户故事 4 - 安全识别和清理本地产物（优先级：P2）

**目标**：把状态、输入、正式成果、日志、可再生成物、缓存和临时文件分开，并提供默认 dry-run 的清理入口。

**独立测试**：清理预览覆盖登记资产但删除数为 0；受保护资产永不成为删除候选。

- [X] T052 [P] [US4] 为保护优先级、类别冲突和 dry-run 增加测试：`00-governance/repository-tools/tests/test_cleanup_safety.py`
- [X] T053 [P] [US4] 建立 `.local-data/state`、`logs`、`cache`、`tmp`、`locks`、`archive` 分区说明：`.local-data/README.md`
- [X] T054 [US4] 先建立新旧状态路径兼容，再按批准清单迁移本地数据库和配置：`04-demo/backend/app/config/`、`.local-data/state/`
- [X] T055 [US4] 检查活动进程后按批准清单归档根 `logs` 和散落日志：`.local-data/logs/legacy-unclassified/`
- [X] T056 [US4] 按批准清单归类预览、截图、检查结果和构建输出：`.local-data/archive/rebuildable/`
- [X] T057 [US4] 按批准清单归类 Office 锁、临时目录和工具缓存：`.local-data/locks/`、`.local-data/tmp/`、`.local-data/cache/`
- [X] T058 [P] [US4] 实现默认 dry-run 的候选清单和大小统计：`00-governance/repository-tools/cleanup-workspace.ps1`
- [X] T059 [P] [US4] 实现按明确类别执行且保护状态/输入/正式成果的清理参数：`00-governance/repository-tools/cleanup-workspace.ps1`
- [X] T060 [US4] 更新忽略规则和外部工具缓存登记；显式跟踪 `.local-data/README.md`，其余 `.local-data/` 内容保持忽略：`.gitignore`、`00-governance/asset-policy/cleanup-policy.json`
- [X] T061 [US4] 运行治理校验和清理 dry-run，记录分类数量、大小、保护、未知项及计时，并断言当前冻结仓库规模下单次总耗时不超过 30 秒：`03-requirements/specs/045-lifecycle-workspace-governance/cleanup-preview.json`
- [X] T062 [US4] 确认 dry-run 前后文件、持久状态和正式成果零变化：`03-requirements/specs/045-lifecycle-workspace-governance/implementation-log.md`

**检查点**：清理能力可用但默认不删除；未知项停在待确认状态。

---

## Phase 8：用户故事 5 - 保持 Demo 与项目流程可用（优先级：P2）

**目标**：切换所有根命令和固定路径，使 Demo、Spec Kit、Skill、部署和验证在新结构下保持兼容。

**独立测试**：运行根统一门禁以及 Docker、Netlify、单服务、Spec Kit 和 Skill 专项，公开行为与冻结基线一致。

- [X] T063 [P] [US5] 更新根 npm workspace、构建、测试和架构命令到新路径：`package.json`、`package-lock.json`
- [X] T064 [P] [US5] 更新后端样例、配置、本地状态和单服务路径兼容：`04-demo/backend/app/`、`04-demo/backend/scripts/`
- [X] T065 [P] [US5] 更新 Docker 构建上下文和忽略规则：`Dockerfile`、`.dockerignore`
- [X] T066 [P] [US5] 更新 Netlify 前端 base/publish、忽略规则和部署测试：`netlify.toml`、`.netlifyignore`、`04-demo/frontend/tests/deploymentContract.test.mjs`
- [X] T067 [US5] 将 Spec Kit 默认路径切到目标规格目录、迁移活动 045 指针并移除过渡回退：`.specify/scripts/powershell/`、`.specify/feature.json`
- [X] T068 [US5] 更新 `speckit-*` Skill 的默认规格路径和说明：`.agents/skills/speckit-*/SKILL.md`
- [X] T069 [US5] 将 Demo 算法解释 Skill 权威内容迁入阶段并保留可发现入口：`04-demo/skills/demo-algorithm-explainer/`、`.agents/skills/demo-algorithm-explainer/SKILL.md`
- [X] T070 [P] [US5] 更新所有当前入口、文档、脚本和测试路径引用：`README.md`、`AGENTS.md`、`agent.md`、`00-governance/`、`01-discovery/`、`02-solution-analysis/`、`03-requirements/`、`04-demo/`、`05-validation/`、`06-delivery/`
- [X] T071 [US5] 增补 045 旧路径映射和历史原文解释：`00-governance/history/path-migration.md`
- [X] T072 [US5] 运行 Spec Kit prerequisites、项目 Skill 发现和工作包命令专项：`03-requirements/specs/045-lifecycle-workspace-governance/quickstart.md`

---

## Phase 9：收敛与交付

- [X] T073 校验批准清单源/目标、哈希、跟踪状态、引用、保留等级和清单外资产：`03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json`
- [X] T074 运行后端、前端、架构、文档、Docker/Netlify、单服务、包体和性能门禁：`03-requirements/specs/045-lifecycle-workspace-governance/implementation-report.md`
- [X] T075 运行 `git diff --check`、密钥文件名、根目录、日志、缓存、锁和未知生成物检查：`03-requirements/specs/045-lifecycle-workspace-governance/implementation-report.md`
- [X] T076 汇总修改文件、工作包、清理预览、验证结果、剩余风险和分批回退：`03-requirements/specs/045-lifecycle-workspace-governance/implementation-report.md`
- [X] T077 对照 spec、plan、tasks、contracts 和 Constitution 执行 `$speckit-converge`：`03-requirements/specs/045-lifecycle-workspace-governance/convergence-report.md`

---

## 依赖与执行顺序

```text
Phase 1 -> Phase 2 -> Phase 3 approval
  -> US1 -> US2 -> US3 -> US4 -> US5 -> Phase 9
```

- T019 是所有物理迁移和清理的硬阻塞点。
- US1 建立真实生命周期所有权；US2 在新所有权上收敛独立工作包。
- US3 依赖 US1/US2 的稳定路径，随后固化未来自动归类。
- US4 可在 US3 后执行，但状态迁移和日志归档必须串行并复核进程。
- US5 依赖全部目标路径稳定；T067 完成后 045 自身迁入新规格目录。
- T077 最后执行。

## 并行机会

- T002～T004、T006～T011 可并行采集或写不同测试。
- T021 的阶段 README 可按文件并行；T022～T029 的物理迁移按批次串行。
- T032～T039 可在不同工作包并行，但不得同时修改共享索引。
- T043～T045、T048～T049 可并行。
- T052～T053 与 T058 可并行准备；实际本地文件移动 T054～T057 串行。
- T063～T066 可并行更新不同平台入口；T067～T069 依赖规格/Skill 边界确认。

## 实施策略

### MVP

完成 Phase 1～3 和 US1：建立真实七阶段根所有权，并证明可以从根目录定位核心资产。即使后续工作包细化尚未完成，也不得恢复旧通用目录作为所有权。

### 完整实施

在 US1 基础上完成工作包、自动归类、安全清理和全部兼容切换。任何清单差异都停止对应批次，不扩大用户在 T019 的授权。

### 格式校验

本文件共 77 个任务；所有任务使用 `- [ ] TNNN [P?] [US?] 描述 + 文件路径` 格式，用户故事任务均带 `[US1]`～`[US5]` 标签。
