# 实施计划：路面实际进度统计

**功能目录**：`077-pavement-actual-progress` | **日期**：2026-09-30 | **规格**：[spec.md](./spec.md)

**状态**：用户已确认，按任务清单实施。沿用当前工作树，不新建或切换 Git 分支。

## 概要

在路面“计划执行”下新增月度实际进度表。复用任务视图的施工段父行、工序子行，左侧固定主数据与汇总列，右侧填写每日完成长度。累计按所有日期汇总，剩余可为负，超量允许保存。

在现有项目主数据 SQLite 中增加独立每日台账，使用稳定工序 ID 关联；不依赖求解结果，不把进度写回场景配置。通过两项 API 完成读取、差量保存，采用主数据版本与台账修订号防止覆盖。具体字段见 [数据模型](./data-model.md) 和 [接口契约](./contracts/progress.md)。

## 技术上下文

- **语言/版本**：当前 `.venv` Python 3.12.14；TypeScript 5.7，React 19，Vite 6（以前端 package.json 为准）。
- **主要依赖**：沿用 FastAPI、Pydantic、sqlite3、React；不新增运行依赖或表格框架。
- **存储**：沿用 `PROJECT_MASTER_DB_PATH` 及默认 `.local-data/state/project-master.db`，schema 2→3 只增加进度表；不写 `scheduler-config.json`。
- **验证**：pytest 临时数据库和 API 测试、Node 领域/组件测试、前端构建、隔离浏览器验收、相关架构及资产检查。
- **目标平台**：现有本地 FastAPI + React 页面。参考演示镜像明确返回路面能力不支持。
- **范围/规模**：约100道工序×最多31天/月；全部日期记录参与累计，表格仅渲染所选月份；不预建虚拟滚动或通用台账框架。
- **约束**：不修改排程目标、资源、工效、班制、任务生成或已有计划；不直接修改真实主数据用于验收；保护当前未提交修改。

## 生命周期归属

引用唯一归属：[`spec.md#生命周期归属`](./spec.md#生命周期归属)。无资产移动。新进度数据为持久状态，不纳入缓存清理。

## 设计决策与实施路径

### D1：复用主数据与任务结构

后端在一致的读取事务中返回当前已确认主数据版本、工序主数据和全部每日记录。前端调用 `pavementTaskGroups(scenario, null)` 复用层级与排序；只在主数据版本相同且无未保存的项目主数据变动时允许填报。物理数量由当前版本的主数据参数提供，不能用求解任务 quantity 代替施工长度。

没有对应结构层 ID 的辅助行只读展示“—”；不重新增加层间配套工序业务。父行只归组。已停用/移除但有实绩的工序进入只读“历史工序记录”。

涉及：`04-demo/frontend/src/domain/pavement.ts`（复用，不计划修改生成规则）、新增 `src/domain/pavementProgress.ts`、后端新增 `app/project_master/pavement_progress.py`。

### D2：独立每日事实与原子保存

schema 增加项目级修订及每日记录表，唯一键为项目＋component_id＋日期。量采用规范十进制文本存储、Python Decimal 运算；接口为数值，前端按千分之一米计算每日累计，校验数值可安全表示，不静默舍入。主数据长度保留原精度，展示格式不改写原值。

读取和保存使用同一 SQLite 事务中的当前版本与台账修订；禁止在事务外先校验再写入。批次检查通过后才应用 changed cells，null 删除、0保留，每个有效改动批次只递增一次修订。累计/剩余不单独持久化。

涉及：`04-demo/backend/app/project_master/schema.py`、`repository.py`（仅在需要复用同一连接的读取入口时小幅调整）、`pavement_progress.py`、`service.py`。

### D3：明确共享接口

新增 GET/PUT `/api/projects/{project_id}/pavement-progress`；GET 返回完整累计所需数据，PUT 只接收改动格和并发令牌，成功返回最新台账视图。项目不存在/无确认版本、字段非法、版本冲突、存储失败分别保留可区分错误。旧 API 和求解契约不变。

涉及：`04-demo/backend/app/contracts/project_master.py`、`app/api/routers/project_master.py`；`04-demo/frontend/src/contracts/projectMaster.ts`、`src/api/projectMasterApi.ts`；`04-demo/tools/demo-api-mirror/api.mts`。

### D4：月表编辑与草稿状态

新增 `04-demo/frontend/src/features/pavementProgress/PavementProgressPanel.tsx` 和同目录 `styles.css`。在 `src/features/layout/WorkspaceNavigation.tsx`、`src/contracts/scheduler.ts` 增加路面菜单，在 `src/app/Workspace.tsx` 接入。

使用语义化表格、固定表头和左侧列、日期输入格、折叠父行和月份切换。每日编辑立即预览累计/剩余；未填不报必填错误。显式保存，保存中禁编，失败保留草稿。面板首次进入后保持挂载，离开菜单只隐藏，避免丢草稿；未保存时注册 beforeunload。进度状态独立，不调用场景 patch，不失效求解结果。

发生409时保留草稿，重新加载后列出改动格的最新已保存值与本地值，由用户明确核对后选择保留或放弃；停用/删除行草稿不能强写。不同项目的数据和草稿隔离，异步旧请求不能覆盖新项目视图。

### D5：兼容与安全升级

以临时 v2 数据库验证新增表升级，主数据版本、内容及导入记录保持一致；重复初始化无副作用，更高未知版本仍拒绝打开。每日记录关联最后保存时的历史主数据版本/工序以保留身份，禁止级联删除实绩。

正式使用新代码前按 SQLite backup API 对实际配置路径做一致性备份；备份落在 `.local-data/state/`、不提交。升级失败停止并留存原库与备份，不自动覆盖或降级。旧程序面对 schema3 保持既有“版本过高”保护；已产生进度后不得用旧库覆盖。

### D6：验证与边界

新增后端 `04-demo/backend/tests/test_pavement_progress.py`、`test_pavement_progress_schema.py`，前端 `04-demo/frontend/tests/pavementProgress.test.mjs`；复用既有主数据测试夹具和测试方式。验证共享契约时扩展 `tests/projectMasterApi.test.mjs`。

新增端点及模块涉及 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`；仅捕获并核对本功能合理差异，不以改基线隐藏既有问题。验证步骤见 [quickstart.md](./quickstart.md)。

## Constitution 检查

| 检查项 | 研究前 | 设计后 |
| --- | --- | --- |
| 业务目标、来源、假设、验收明确 | 通过：用户4项要求与超量答复 | 通过：FR/SC及数值例已落到接口和验证 |
| 算法/资源/工期影响明确 | 通过：本次不改变排程 | 通过：独立保存，不触发重排或结果失效 |
| 共享契约和异常/兼容完整 | 通过：识别为跨端持久化变更 | 通过：字段、状态码、事务、升级及镜像见契约 |
| 复用现有结构，无无关依赖 | 通过 | 通过：现有DB/路由/菜单/任务投影，无新框架 |
| 来源评审与确认阶段真实 | 通过：用户需求及代码核对，无独立评审 | 通过：尚未宣称已确认实施，等待tasks门禁 |
| 唯一资产归属、用户状态保护 | 通过 | 通过：只增表、临时库验收、升级备份，无清理 |

无需要豁免的复杂度违反项。仓库没有 agent context 更新脚本，不伪造该步骤，也不为本功能改写通用 Agent 规则。

## 文档结构与交付顺序

本目录：`spec.md` → `research.md` / `plan.md` → `data-model.md` / `contracts/progress.md` / `quickstart.md` → `tasks.md`。

按共享契约和台账基础、只读月表、每日编辑保存、版本/历史保护、定向验收顺序实施。任务清单确认前只生成本目录文档及规格索引，不修改产品源码或运行库。

实施补充：为落实D4的未保存主数据保护，主数据编辑组件增加dirty状态回传（ProjectMasterDataWorkspace、PavementMasterTable、PavementSectionLayers、PavementSectionHandover），不改变主数据保存和排程规则；邻近pavementMaster.test.mjs同步模拟effect。
