# 任务清单：结构物匹配的中文资源目录

**输入**：`03-requirements/specs/050-structure-matched-resource-catalog/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门禁**：本清单及下方一致性检查须由用户确认后，才能执行 `$speckit-implement`。

## Phase 1：共享基础

**目标**：建立自动匹配和中文显示共同依赖的单一常量来源。

- [x] T001 在 `04-demo/frontend/src/domain/constants.ts` 增加全部现有内置可配置资源类型的稳定中文名称、项目主数据上部结构到排程构件类型的映射以及统一排除类型集合，名称至少覆盖旋挖钻机、回旋钻机、冲击钻机、人工挖孔班组、承台模板、墩柱模板、盖梁模板和连续梁班组，且不引入架桥机/梁场类型

**检查点**：匹配规则和各页面可从同一常量模块读取类型映射与中文名称。

---

## Phase 2：用户故事 1 - 按工点结构自动展示可能资源（优先级：P1）

**目标**：所选桥梁工点只展示其启用结构和采用工艺可能使用的资源，不依赖任务生成，也不回退到全项目目录。

**独立测试**：用旋挖/回旋/冲击/人工挖孔、连续梁、普通下部结构、禁用构件、重复类型和空结构工点夹具验证输出集合及页面状态。

- [x] T002 [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加工点结构投影测试，覆盖四种桩基方法只匹配实际方法、`continuous_unit` 匹配连续梁班组、承台/墩柱/盖梁映射、禁用构件过滤、无映射为空、同类型去重和等价输入稳定排序
- [x] T003 [US1] 在 `04-demo/frontend/src/domain/resources.ts` 实现纯工点结构资源投影：读取 `ProjectMasterWorkpoint` 启用结构/构件，按显式 `method_id` 或等价参数优先、唯一默认工艺兜底，复用 `defaultResourceTypeForProcess`，排除越界类型并输出确定性去重类型集合
- [x] T004 [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 增加资源页详情读取的源代码契约测试，要求请求身份绑定 `project_data_version_id + workpoint_id`、乱序响应丢弃、加载/失败/空态不回退全目录，并禁止继续使用 `generated.schedule_input.tasks` 计算默认资源
- [x] T005 [US1] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 复用 `getProjectMasterWorkpoint` 按所选工点懒加载详情，维护版本/工点请求身份和重试状态，以结构投影替代任务资源及全目录回退，并将匹配建议与当前工点已配置类型合并展示
- [x] T006 [US1] 在 `04-demo/frontend/src/app/Workspace.tsx` 移除 `ResourcesTab` 已不再需要的 `generated` 输入，同时保留现有工点列表版本请求、保存流程和场景指纹失效行为

**检查点**：即使资源池为空、未生成任务，工点仍能按结构得到正确建议；详情失败或空结构不会显示全项目资源。

---

## Phase 3：用户故事 2 - 使用中文资源名称（优先级：P1）

**目标**：默认建议、补充目录、已配置行和资源助手对标准类型使用一致的中文主名称。

**独立测试**：验证标准类型中文覆盖、中文池名优先、英文/空标签不覆盖内置名称，以及未知自定义类型显示中文未命名提示和代码。

- [x] T007 [US2] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加中文目录测试，覆盖全部内置类型含中文字符、`rotary_drill → 旋挖钻机`、`cap_beam_team → 盖梁模板`、`cast_in_place_continuous_beam_team → 连续梁班组`、中文池名优先、英文或空标签回退内置名称、未知自定义类型中文未命名提示及代码保留
- [x] T008 [US2] 在 `04-demo/frontend/src/domain/resources.ts` 收敛 `resourceTypeLabel` 和 `resourceCatalogProjection` 的名称解析优先级为“已配置中文标签 → 内置中文名称 → 中文未命名提示”，并让完整补充目录对标准类型使用相同中文名称
- [x] T009 [P] [US2] 在 `04-demo/frontend/src/domain/resourceAssistant.ts` 删除私有 `defaultResourceTypeLabels` 重复表，改用 `04-demo/frontend/src/domain/resources.ts` 的统一中文名称解析，保持资源助手现有计算与池身份逻辑不变
- [x] T010 [P] [US2] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 将建议行、已配置行和补充下拉的主名称统一为领域层中文名称，类型代码只作为次级信息，并为未知自定义类型保留可识别代码

**检查点**：标准资源不再以英文代码作为主名称，各资源入口没有相互冲突的名称表。

---

## Phase 4：用户故事 3 - 自动匹配不等于自动投入（优先级：P2）

**目标**：结构匹配只产生数量和上限均为 0 的虚拟建议，用户明确操作后才保存工点独享资源；既有记录不被结构变化删除。

**独立测试**：查看和切换建议不产生资源池；添加后只生成当前工点唯一独享池；不再匹配的既有记录仍显示且字段不变。

- [x] T011 [US3] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加建议/配置边界测试，覆盖虚拟行 `quantity=0`、`max_quantity=0`、不自动启用/持久化、同工点同类型唯一 `WORKPOINT_EXCLUSIVE`、当前不匹配的既有池仍可见，以及不创建 `PROJECT_SHARED`
- [x] T012 [US3] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 固化建议行数量和上限为 0、状态为未配置且不在渲染时写入场景；仅在用户编辑或添加时创建/更新当前工点唯一独享池，并保留所有当前工点既有池字段
- [x] T013 [US3] 更新 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 的工点详情网络夹具和页面断言，覆盖中文名称、旋挖桩基、连续梁、无结构空态、A→B/版本切换旧响应丢弃、只查看不保存、明确添加为工点独享，以及旧配置继续可见

**检查点**：建议与实际投入边界清晰，结构变化不会静默改写用户资源数据，也不会触发共享资源计算。

---

## Phase 5：收敛验证

**目标**：用一次定向验证批次证明核心目标，并记录非核心环境风险。

- [x] T014 运行 `node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs`，修正由本功能导致的领域、中文名称和源代码契约失败，记录退出结果
- [x] T015 仅运行一次 `node --test 04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`；修正由本功能导致的页面失败；若失败被证实仅为系统浏览器/CDP 环境且 T014、T016 已覆盖核心目标，则记录证据后继续，不深挖与核心目标无关的环境问题
- [x] T016 依次运行 `npm.cmd run typecheck` 和 `npm.cmd run build`，修正本功能引入的类型或构建失败；对有证据表明与本功能无关且不影响核心目标的问题记录为剩余风险
- [x] T017 运行 `python 00-governance/repository-tools/validate_docs.py`，修正 050 规格资产相关失败，并记录其他既有工作树问题而不改动无关资产

---

## 依赖与执行顺序

### 阶段依赖

- T001 是全部故事的共享基础。
- 用户故事 1 按 T002 → T003 → T004 → T005 → T006 执行，先固定投影和请求契约，再接入页面。
- 用户故事 2 在 T003 后执行 T007 → T008；T009 与 T010 在 T008 后可并行，但 T010 同时要求 T005 已完成。
- 用户故事 3 在 T005、T008 后执行 T011 → T012 → T013。
- T014–T017 在全部故事实现后执行；不再追加第二次全量门禁。

### 并行机会

- T009 与 T010 修改不同文件，在 T008 完成后可并行。
- 文档阶段已完成，不与实施任务并行改写业务规则。
- 其余任务存在同文件或行为依赖，不标记并行，避免覆盖当前脏工作树中的相关改动。

## 一致性检查

### 需求与成功标准覆盖

- **US1 / FR-004–FR-009、FR-014、FR-016 / SC-002–SC-005**：T002–T006、T013–T016。
- **US2 / FR-001–FR-003、FR-013 / SC-001**：T001、T007–T010、T013–T016。
- **US3 / FR-010–FR-012、FR-015 / SC-006–SC-007**：T011–T016。
- **FR-017 / SC-008**：T002、T004、T007、T011、T013–T017。
- 三个用户故事的全部验收场景均有对应领域测试、页面契约或运行时场景；没有未覆盖的可实施需求。

### 设计与边界一致性

- 任务只修改 `plan.md` 声明的前端源码和测试路径，不新增后端接口、模型、迁移、依赖或共享资源。
- 工点详情接口只读取，不改变 API schema 或 Demo 镜像；版本/工点失败态禁止全目录回退。
- 建议与持久化严格分离；数量 0 仍表示没有实际资源，求解器和共享输入兼容逻辑不修改。
- 验证只有一个定向批次和一次运行时尝试；首次相关失败必须修正，已证实的非核心环境失败可记录后继续。

**检查结果**：通过。未发现冲突术语、缺失依赖、越界路径、重复全量验证或未覆盖需求；可以进入用户确认门禁。

## 实施与验证记录

**实施日期**：2026-07-19

- T001–T013：实现与测试资产均已写入清单指定路径；未新增后端接口、持久化字段、共享资源或求解器变更。
- T014：`node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 通过，11/11；补齐全部 16 类内置中文名称覆盖后定向复跑仍为 11/11。
- T015：按清单仅尝试一次真实页面运行时验证；FastAPI/Vite 健康、Chrome 150 启动成功，但 `Page.enable` 在进入页面前等待 CDP 60 秒超时。运行记录显示业务请求、DOM 转换和断言均尚未开始，归类为非核心系统浏览器/CDP环境失败；证据位于 `.local-data/logs/050-structure-matched-resource-catalog/runtime/20260719103752-resource-workpoint-runtime/`。
- T016：`npm.cmd run typecheck` 退出码 0；`npm.cmd run build` 退出码 0。Vite 仅报告既有的大于 500 kB chunk 警告。
- T017：`python 00-governance/repository-tools/validate_docs.py` 退出码 0，输出 `documentation links and API facts: OK (14 documents)`。
- 风险聚焦检查：目标源码和测试执行 `git diff --check` 退出码 0；未改动工作树中的无关治理、客户资料和其他规格资产。

**完成判定**：核心验收已由领域/契约测试、类型检查和生产构建证明；真实浏览器场景保留上述环境风险，不阻断本功能完成。
