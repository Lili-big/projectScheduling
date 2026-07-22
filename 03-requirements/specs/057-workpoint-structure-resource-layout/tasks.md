# 任务清单：工点结构物与资源左右分栏配置

**输入**：`03-requirements/specs/057-workpoint-structure-resource-layout/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门禁**：本清单及下方一致性检查须由用户确认后，才能执行 `$speckit-implement`。

## Phase 1：用户故事 1 - 结合结构物汇总估算资源（优先级：P1）

**目标**：所选工点左侧按六类下部结构、参数、工艺和单位形成稳定汇总，右侧资源配置可与结构依据同屏对照。

**独立测试**：用六类构件、重复签名、不同桩径/工艺/单位、禁用/零数量、缺失参数、未知工艺和乱序输入夹具验证分类、分组、数量、格式与顺序。

- [x] T001 [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加结构物汇总领域测试，覆盖六类固定顺序与页面中文名、`enabled=true && quantity>0` 过滤、相同签名累加、参数/工艺/单位差异分组、`旋挖钻-φ1.8×5根`、`3×4×12m×2个` 等价输出、未知/缺失工艺诊断和等价输入稳定排序
- [x] T002 [US1] 在 `04-demo/frontend/src/domain/resources.ts` 实现 `WorkpointStructureSummaryGroup` / `WorkpointStructureSummaryItem` 纯派生逻辑，复用现有显式工艺优先与唯一默认工艺边界，规范化非工艺参数并按类型、参数、工艺、单位聚合数量，不写入场景资源
- [x] T003 [US1] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 增加资源页结构契约测试，固定“结构物信息”在“资源配置”之前、详情就绪后同源渲染、没有六类构件的左侧空态，以及不得从结构数量自动写入 `quantity` / `max_quantity`
- [x] T004 [US1] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 将当前详情投影为结构物汇总，并在工点导航/目录补充下方渲染左侧只读结构信息与右侧资源区；保持当前版本/工点请求身份、详情重试和旧响应丢弃逻辑不变
- [x] T005 [US1] 在 `04-demo/frontend/src/features/resources/styles.css` 增加结构汇总分类/条目和响应式双栏样式，桌面左右并排，窄屏结构在前资源在后，并移除旧资源表格 900px 最小宽度造成的横向布局依赖

**检查点**：即使未生成任务或资源池为空，当前工点也能从主数据详情得到正确结构汇总；只查看汇总不会产生资源投入。

---

## Phase 2：用户故事 2 - 简化工点资源录入（优先级：P1）

**目标**：右侧只保留中文资源名称和必要数字输入，当前投入数量唯一决定工点独享资源是否启用。

**独立测试**：验证 0→正数、正数→0 和两类历史矛盾状态；页面不得出现资源技术代码、字段表头、状态列或启用控件，同时保留目录补充、保存、显式删除和无障碍输入语义。

- [x] T006 [US2] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先增加工点独享资源规范化测试，覆盖 `quantity=0 => enabled=false`、`quantity>0 => enabled=true`、`max_quantity>=quantity`、历史矛盾状态按数量收敛、零数量不删除记录，以及 `PROJECT_SHARED` 兼容启用语义不变
- [x] T007 [US2] 在 `04-demo/frontend/src/domain/resources.ts` 收紧 `normalizeResourcePoolForWorkspace`：仅对带明确 `workpoint_id` 的 `WORKPOINT_EXCLUSIVE` 记录由规范化数量派生 `enabled`，保留公共字段、共享记录和既有其他规范化行为
- [x] T008 [US2] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 增加资源页源码契约测试，禁止资源类型 `<code>`、可见 `<thead>` / 字段表头、状态列和启用复选框，同时要求中文名称、当前投入/可增上限的 `aria-label` 或等价语义、目录补充和显式删除入口继续存在
- [x] T009 [US2] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 将右侧表格改为紧凑资源项，删除技术代码、字段表头、状态列和启用开关；编辑/新增时让兼容 `enabled` 与当前投入同步，并保留建议项 0/0、中文名称、目录补充、保存和显式删除行为
- [x] T010 [US2] 在 `04-demo/frontend/src/features/resources/styles.css` 完成右侧紧凑资源项的数字控件、操作和长中文名称布局，确保左右并排及窄屏下不依赖字段标题且不遮挡输入/删除操作

**检查点**：用户不再配置独立启用状态，资源数量和兼容字段不会出现矛盾，既有共享读取边界未扩展。

---

## Phase 3：用户故事 3 - 稳定切换与异常识别（优先级：P2）

**目标**：快速切换、详情失败和结构空态下，左右区块始终属于同一当前工点，已配置资源不因结构空态丢失。

**独立测试**：模拟 A→B 乱序响应、详情失败重试、无六类构件但有本地资源和只查看建议四种状态，验证左右数据、错误/空态和持久化边界。

- [x] T011 [US3] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 扩展页面状态源码契约，要求结构汇总与资源建议共用 `project_data_version_id + workpoint_id + 最新请求` 身份，失败不回退全项目目录，结构空态不隐藏当前工点既有资源
- [x] T012 [US3] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 收敛双栏加载、失败、重试、结构空态和资源空态渲染，保证切换工点时不保留旧结构摘要、空结构不自动清空/删除右侧资源、只查看不持久化建议
- [x] T013 [US3] 在 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 更新当前工点详情夹具和页面断言，覆盖左右区块、桩基/承台汇总、无资源字段表头与开关、数量派生状态、A→B/版本乱序、详情失败、结构空态保留既有资源及建议不隐式保存

**检查点**：全部用户故事可在同一当前工点上下文中工作，异常状态不制造错误结构或资源数据。

---

## Phase 4：收敛验证

**目标**：用一次风险匹配的定向批次证明结构汇总、资源数量语义和页面构建，并记录非核心环境风险。

- [x] T014 运行 `node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs`；首次失败后修正本功能相关的分组、资源规范化或页面源码契约问题并复验，不因可修正的相关失败暂停实施
- [x] T015 仅运行一次 `node --test 04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`；若业务页面已加载且核心断言失败，修正相关实现并复验；若证据证明失败发生在业务页面加载前且仅属于系统浏览器/CDP 环境，记录日志后继续，不深究无关设施问题
- [x] T016 依次运行 `npm.cmd --prefix 04-demo/frontend run typecheck` 和 `npm.cmd --prefix 04-demo/frontend run build`；修正本功能引入的类型或构建失败，对有证据表明无关且不影响核心目标的问题记录为剩余风险
- [x] T017 运行 `python 00-governance/repository-tools/validate_docs.py` 并对 057 规格和目标源码/测试执行 `git diff --check`；修正本工作项相关文档或空白错误，保留并记录无关脏工作树问题

---

## 依赖与执行顺序

### 阶段依赖

- 用户故事 1 按 T001 → T002 → T003 → T004 → T005 执行，先固定领域汇总，再接入页面与布局。
- 用户故事 2 在 T002 后按 T006 → T007 → T008 → T009 → T010 执行；T009 同时依赖 T004，避免重复改写页面结构。
- 用户故事 3 在 T004、T009 完成后按 T011 → T012 → T013 执行。
- T014–T017 在全部故事实现后执行；不追加第二次全量测试门禁。

### 并行机会

- 本功能主要修改 `resources.ts`、`ResourcesTab.tsx`、`styles.css` 和同一个定向测试文件，存在明确顺序与脏工作树重叠风险，不标记源码任务并行。
- 运行时测试 T013 可在领域与页面源码契约完成后独立准备，但必须在 T012 后确认最终 DOM。
- 文档已在实施前完成，不与代码实现并行改写业务规则。

## 一致性检查

### 用户故事、需求与成功标准覆盖

- **US1 / FR-001–FR-007、FR-014 / SC-001–SC-002**：T001–T005、T013–T016。
- **US2 / FR-008–FR-013、FR-016–FR-017 / SC-003–SC-004、SC-006**：T006–T010、T013–T017。
- **US3 / FR-015 / SC-005**：T011–T016。
- 六类结构顺序、签名维度、数量/单位、缺失数据、未知工艺、响应式布局、中文名称、字段简化、数量派生启用、建议不持久化、历史保留、失败/空态/乱序和非共享/非求解边界均有实现任务与定向验证。

### 设计与边界一致性

- 所有实施路径均来自 `plan.md`；不新增后端、API、持久化、求解器、共享资源、依赖或目录。
- `enabled` 字段保留，只对规范工点独享资源派生；共享/兼容读取不变，避免公开契约漂移。
- 结构汇总为只读派生信息，不写资源数量；资源建议与实际配置边界继续沿用 feature 050。
- 失败修正遵循仓库契约：相关失败修正后复验；只有证据充分且不影响核心目标的环境/无关失败才记录后继续。
- `setup-tasks.ps1` 执行时共享 `.specify/feature.json` 已被并行工作项指向 053；本清单使用脚本返回的权威模板并直接针对现存 057 规格生成，没有覆盖 053 指针或写入其资产。

**检查结果**：通过。17 个任务覆盖全部用户故事、功能需求、成功标准和计划决策；未发现冲突术语、缺失依赖、越界路径、重复全量验证或阻断澄清。可以进入用户确认门禁。

## 实施与验证记录

**实施日期**：2026-07-21

- T001–T013：已在清单指定的前端领域、页面、样式和两个资源定向测试文件中完成。结构汇总只读取当前工点详情；没有新增后端接口、持久化字段、共享资源、依赖或求解器规则。
- T014：`node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 首次测试先行运行按预期暴露缺失汇总函数、旧启用语义和旧表格 DOM；完成实现后复验退出码 0，15/15 通过。
- T015：按清单只执行一次真实页面运行时尝试。FastAPI/Vite 健康且 Chrome 150 启动成功，但在业务页面创建前 `Page.enable` 等待 CDP 60 秒超时。证据中 `transitions=[]`，保存、生成、工点列表和工点详情请求均为 0，说明没有进入 057 业务断言；归类为非核心系统浏览器/CDP 环境失败。证据：`.local-data/logs/050-structure-matched-resource-catalog/runtime/20260721002657-resource-workpoint-runtime/resource-workpoint-runtime-summary.json`。
- T016：`npm.cmd --prefix 04-demo/frontend run typecheck` 退出码 0；`npm.cmd --prefix 04-demo/frontend run build` 退出码 0。Vite 仅报告既有的大于 500 kB chunk 警告。
- T017：`python 00-governance/repository-tools/validate_docs.py` 退出码 0，输出 `documentation links and API facts: OK (14 documents)`；目标源码和测试 `git diff --check` 退出码 0，仅有 Git 的 LF/CRLF 提示。
- 并发保护：实施期间 `.specify/feature.json` 仍由并行工作项 053 持有；057 直接按已确认资产执行，没有覆盖共享指针或修改 053 文件。

**完成判定**：17/17 任务完成。结构汇总、数量派生启用、页面源码契约、类型检查和生产构建均有可重复通过证据；真实浏览器视觉/交互验收保留上述 CDP 环境风险，不阻断核心功能完成。
