# 实施任务：路面实际进度统计

**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[接口契约](./contracts/progress.md)、[验证指南](./quickstart.md)。

**状态**：已完成，14/14项有实施与验收证据。

## 共享基础（2项）

- [x] T001 在 `04-demo/backend/app/contracts/project_master.py` 和 `04-demo/frontend/src/contracts/projectMaster.ts` 定义台账视图、主数据行、日记录及差量保存请求，包含双版本令牌、可空清除量、精度/日期/额外字段校验；按 `contracts/progress.md` 保留旧契约不变。
- [x] T002 在 `04-demo/backend/tests/test_pavement_progress_schema.py` 先定义旧v2库增量升级、重复初始化、高版本拒绝及原主数据内容不变的测试；在 `04-demo/backend/app/project_master/schema.py` 实现schema3两张进度表、唯一键及历史身份RESTRICT外键；只在必要时扩展 `04-demo/backend/app/project_master/repository.py` 同连接读取入口，复用既有事务而不触碰真实库。

## US1：查看与任务结构一致的月表（P1，4项）

独立验收：无求解结果即可看到主数据工序，量/宽厚只读，月表层级和任务视图一致。

- [x] T003 [US1] 在 `04-demo/backend/tests/test_pavement_progress.py` 和 `04-demo/frontend/tests/pavementProgress.test.mjs` 先加入只读投影用例：当前启用ID/排序、无解可用、主数据施工长度与工效单位解耦、缺失参数为null/“—”、空项目/空记录/读取失败区分、父行不重复累计、辅助行只读；断言缺少实现后在本故事完成时运行定向用例。
- [x] T004 [US1] 在新增 `04-demo/backend/app/project_master/pavement_progress.py` 实现同一读取快照中的当前主数据和全日期记录查询、Decimal累计及负剩余；通过 `04-demo/backend/app/project_master/service.py` 与 `04-demo/backend/app/api/routers/project_master.py` 接入GET，映射404/422/503，不依赖任务生成成功或求解结果。
- [x] T005 [US1] 在 `04-demo/frontend/src/api/projectMasterApi.ts` 增加台账读取方法，在新增 `04-demo/frontend/src/domain/pavementProgress.ts` 复用 `04-demo/frontend/src/domain/pavement.ts` 的 `pavementTaskGroups(scenario, null)` 组织父子行并按component_id联接当前主数据尺寸，校验版本匹配；生成本地当前月份及上/下月日期，不修改现有任务投影语义。
- [x] T006 [US1] 在新增 `04-demo/frontend/src/features/pavementProgress/PavementProgressPanel.tsx`、同目录 `styles.css` 实现月表、固定表头/左列、滚动、父行折叠和加载/空态/重试；在 `04-demo/frontend/src/contracts/scheduler.ts`、`src/features/layout/WorkspaceNavigation.tsx`、`src/app/Workspace.tsx` 接入仅路面的“计划执行→实际进度统计”，首次访问后保持面板挂载；按规格列序展示，当前仅只读，无额外总体汇总指标。

## US2：每日填报、累计与保存（P1，3项）

独立验收：1790m工序跨月录入300+450+100后累计850、剩余940；超量可存并读回。

- [x] T007 [US2] 在 `04-demo/backend/tests/test_pavement_progress.py`、`04-demo/frontend/tests/pavementProgress.test.mjs` 先加入跨月数值样例、更正非追加、清空与0区分、负剩余、0.1+0.2、精度/非法值、刷新/重新建立repository读回、失败保留草稿和未保存提醒的验证；实现前确认对应能力缺失，随后只运行本批定向测试。
- [x] T008 [US2] 在 `04-demo/backend/app/project_master/pavement_progress.py` 实现原子差量保存、同事务双版本比较、当前启用工序及项目校验、重复键拒绝、修订递增和无变更不递增；在 `04-demo/backend/app/project_master/service.py`、`app/api/routers/project_master.py` 接入PUT及错误码，在 `04-demo/frontend/src/api/projectMasterApi.ts` 增加保存方法；超量不拒绝，不产生主数据版本、不触发排程失效。
- [x] T009 [US2] 在 `04-demo/frontend/src/domain/pavementProgress.ts` 实现按日键的草稿覆盖/清空、全日期精确累计与changed cells生成；在 `04-demo/frontend/src/features/pavementProgress/PavementProgressPanel.tsx`、`styles.css`、`src/app/Workspace.tsx` 接入每日数值编辑、统一保存、超量标注、dirty/saving/saved/error、保存中禁编、菜单/月切换保留草稿及beforeunload；主数据尺寸与累计保持只读，进度状态独立于场景patch。

## US3：主数据更新、历史与并发保护（P2，3项）

独立验收：改名/改长度不丢日记录，停用可查看历史；并发保存后写入方冲突且整批回滚。

- [x] T010 [US3] 在 `04-demo/backend/tests/test_pavement_progress.py` 先加入版本变更、两请求/两连接同revision、主数据确认与保存串行、跨项目/禁用/重复格整批拒绝、历史ID恢复、同名新ID不迁移、原主数据版本与内容未改的测试；在 `04-demo/frontend/tests/pavementProgress.test.mjs` 加入409草稿保留、重读核对、旧请求不能覆盖新项目、未保存主数据禁编用例。
- [x] T011 [US3] 在 `04-demo/backend/app/project_master/pavement_progress.py` 实现已停用/移除但有记录工序的只读历史投影，移除项从最后记录关联的历史版本取标识/尺寸；在 `04-demo/frontend/src/features/pavementProgress/PavementProgressPanel.tsx`、`styles.css` 显示“历史工序记录”和来源状态，不清除/自动迁移数据，原ID恢复后返回当前表。
- [x] T012 [US3] 在 `04-demo/frontend/src/domain/pavementProgress.ts`、`src/features/pavementProgress/PavementProgressPanel.tsx`、`src/app/Workspace.tsx` 实现版本冲突冻结与重新加载核对：明确呈现每个改动格的服务端值/本地值，经用户选择后才能采用新令牌保存；失效ID禁止强写；隔离项目草稿与异步请求，未保存主数据或主数据版本不匹配时提示处理后再填报，失败不伪装成全0。

## 共享契约及集成验收（2项）

- [x] T013 在 `04-demo/tools/demo-api-mirror/api.mts` 对新增GET/PUT路径返回既有422 `PAVEMENT_FEATURE_NOT_SUPPORTED`；在 `04-demo/frontend/tests/projectMasterApi.test.mjs` 扩展请求/响应及错误映射用例、在 `04-demo/frontend/tests/pavementProgress.test.mjs` 验证镜像拒绝和bridge菜单兼容；保证旧主数据/配置/接口继续可用，不伪造持久化成功。
- [x] T014 按 `03-requirements/specs/077-pavement-actual-progress/quickstart.md` 完成尚未运行的定向检查、一次前端构建和隔离浏览器验收，核对约100工序×31天及宽窄屏、保存前后求解结果/主数据/资源/配置不变；用现有捕获脚本更新并核对 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 的新增差异并执行check与资产验证。在实际服务使用新schema前对真实配置路径做SQLite一致性备份至 `.local-data/state/`，按 `04-demo/runtime/README.md` 处理必要服务操作，保留用户原页；仅将实际结果、备份位置和已知非本功能失败写入本文件并更新 `03-requirements/specs/README.md`，不得重复全量测试或用基线掩盖异常。

## 依赖与执行方式

- T001→T002→US1（T003→T004→T005→T006）→US2（T007→T008→T009）→US3（T010→T011→T012）→T013→T014。
- 测试先定义，再完成对应能力后执行相关批次。US3测试若发现事务实现缺陷，在T008涉及路径内修复根因，不能仅调整断言。
- 共14项：共享基础2、US1 4、US2 3、US3 3、集成2。主要改动跨故事复用同一组文件，不标记可并行任务，不另起审查/分析阶段。
- 用户确认本清单后进入 `$speckit-implement`；确认前不运行新schema、不写真实进度、不改产品代码。

## 一次性一致性核对

### FR与成功标准覆盖

| 来源 | 对应任务/证据 |
| --- | --- |
| FR-001 导航与两级行 | T003、T005、T006 |
| FR-002 当前主数据、稳定任务结构、无求解依赖 | T003—T006、T012 |
| FR-003 长度/宽厚/桩号及米口径 | T001、T003—T006 |
| FR-004 全日期累计、只填日量、缺失值 | T004、T007—T009 |
| FR-005 月份、固定列、滚动、折叠 | T005、T006、T014 |
| FR-006 日期/数值精度、替换、清空、0 | T001、T007—T009 |
| FR-007 超量及负剩余 | T004、T007—T009 |
| FR-008 独立持久化、差量原子写、重建读回 | T002、T007、T008、T010 |
| FR-009 全部状态、失败/冲突草稿、离页提醒 | T006、T007、T009、T010、T012 |
| FR-010 稳定身份、版本变更、历史保留 | T002、T010—T012 |
| FR-011 归属/版本/修订校验、拒绝部分提交 | T001、T008、T010、T012 |
| FR-012 契约、镜像、旧库/配置兼容 | T001、T002、T013、T014 |
| SC-001 层级一致、无解填报、只读列 | T003—T006、T014 |
| SC-002 跨月/更正/清空/0数值例 | T007—T009 |
| SC-003 超量及精确小数读回 | T007—T009 |
| SC-004 原子冲突、隔离、版本/停用、重建 | T002、T007、T010—T012 |
| SC-005 百工序月表、保护用户数据 | T006、T014 |

### 场景、设计决策与边界覆盖

| 来源 | 对应任务 |
| --- | --- |
| US1验收1—5 | T003—T006；布局实测T014 |
| US2验收1—6 | T007—T009；浏览器离页/失败T014 |
| US3验收1—5 | T002、T008、T010—T012；原配置不变T014 |
| D1主数据与投影 | T003—T006、T011 |
| D2独立事实/事务/精度 | T001、T002、T004、T007—T010 |
| D3共享API | T001、T004、T008、T013 |
| D4月表与草稿状态 | T005、T006、T009、T012 |
| D5增量升级与备份 | T002、T010、T014 |
| D6验证与架构 | T003、T007、T010、T013、T014 |
| 空态/读取失败/空白中性/宽厚缺失/辅助行只读 | T003、T006、T009 |
| 默认本地月、任意有效月份、不禁未来日 | T001、T005、T007 |
| 不同项目/旧异步返回/主数据未保存 | T008、T010、T012 |
| 无额外总体汇总/导入导出/排程改造 | T006、T014，范围约束 |
| 响应丢失后重试不重复追加 | T008双版本比较、T010与T012冲突核对 |

**核对结论**：FR-001—012、SC-001—005、全部故事验收及D1—D6均有任务覆盖；依赖及目标路径与plan一致，无无源任务或覆盖缺口。未新增算法/资源模型、依赖或权限体系。该结论只表示设计一致，不是实现通过。

## 证据与未覆盖事项

- 2026-09-30：规格、计划、数据模型、接口、验证指南和本任务清单已生成；没有实施源码，未运行功能测试或迁移真实库。
- 规划验证：`.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py` 退出0，仓库卫生及依赖基线通过。
- 规划验证：`.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py --json` 退出1，共9处已有 `missing-workpackage-reference`：7处位于 `01-customer-validation` 的历史验证成果，2处位于 `04-demo/standalone/json-task-viewer` 的历史输入/输出；本次077目录无违规，未修改无关引用。
- 文档检查：7份Markdown、14个连续任务ID、故事任务数量4/3/3，文档相对链接无断链；检查退出0。
- 未覆盖：实际API、数据库升级和浏览器功能均待用户确认后实施验证；不得将上述文档检查视为功能通过。


## 实施证据（2026-09-30）

- 用户确认“确认实现”后已执行一次implement前置检查。保护既有075/076及其他未提交修改，未重排历史规格或创建新分支。
- 已实现独立每日台账、GET/PUT、月表、全部日期累计、0/清空、负剩余超量、草稿保留和并发核对、历史工序只读；默认当前月，约100工序×31天可用。
- 为落实T012的“未保存主数据禁切换”，补充 `04-demo/frontend/src/features/projectMasterData/ProjectMasterDataWorkspace.tsx`、`PavementMasterTable.tsx`、`PavementSectionLayers.tsx`、`PavementSectionHandover.tsx` 的编辑状态回传，并提供移交条件撤销；不改主数据保存业务口径。更新邻近测试 `04-demo/frontend/tests/pavementMaster.test.mjs` 的effect模拟并验证失败后仍为dirty。
- 测试先行：schema升级与新API三个样例初次按预期失败（v2及路由缺失）；前端新领域模块缺失时用例按预期失败，随后实施对应能力。
- 后端定向命令见quickstart：首轮22通过、1处既有失败；随后新增“主数据确认不能穿插进度写事务”定向测试1通过。共23项通过，其中本功能新增16项。既有失败为 `test_project_master_api.py::test_template_import_batch_query_and_cancel` 仍预期4张工作表，而现有模板含“线路关系”共5张；git HEAD断言及未改动workbook.py均确认与本功能无关，不修改该测试来掩盖问题。
- 前端进度/API/任务结构定向测试17/17通过；主数据邻近测试初次9通过1失败，原测试仅模拟useState、缺少新用到的useEffect，修复模拟后仅重跑该用例通过。共27项独立前端用例通过。
- `npm run build`：初次发现目标库不支持Object.hasOwn，已改为兼容写法；后续各相关代码批次构建通过，最终产物index-KrwxlJWb.js。保留既有大chunk提示，不引入无关拆包改造。
- 浏览器隔离数据库 `.local-data/state/progress-077-acceptance-20260930-111853.db`，25施工段、100工序：300+450+100跨月累计850、剩余940；跨菜单草稿保留；超量1800保存并重开显示-10及超量10；两页409冲突保留320本地草稿并可核对/采用服务器300；1024px下固定工序列并能滚动到31日；未保存主数据阻止菜单切换、撤销后可进入。截图 `.local-data/logs/20260930-111906-496/progress-wide.jpg`。
- 实际数据库已在schema修改前用SQLite backup API备份到 `.local-data/state/project-master-before-077-20260930-111036.db`；schema2→3新增两表。升级后与备份逐表比对15张原业务表完全一致，真实项目日记录0条；scheduler-config.json哈希未变，未向真实项目填写测试量。
- 已确认并精确重启本项目端口8000旧进程51384；新启动器37956，日志 `.local-data/logs/20260930-112646-786/backend-progress-077.*.log`。原用户页未刷新，新页签打开真实项目的实际进度统计。
- 架构基线捕获：后端仅74→76新增两项API，旧路由条目全部保留；前端仅构建体积更新，无旧契约变化。

- 最终检查：后端与前端架构check均退出0；validate_repository退出0。生命周期校验仍为同一9处历史工作包引用缺失，无077新增问题。git diff --check发现本次契约文件末尾多余空行，已修正后通过。
- 真实项目只读验收：19个施工段、95道启用工序、9月2850个日格；长施工段名称按固定列宽换行，九个固定列实测宽度42/66/172/130/82/82/102/56/56 px。最终截图 `.local-data/logs/20260930-112646-786/actual-progress-page.jpg`。真实进度无测试录入，原用户标签页未刷新。
- 本次隔离测试服务（8087，启动器41120、服务11424）已停止；生产本地服务8000保留。测试库和运行日志保留，不自动删除。
- T014完成：未运行与本功能无关的全量求解测试；已有模板断言和9处历史文档引用作为非核心问题留存，不影响新增进度页面验收。
