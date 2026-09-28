# 实施计划：路床移交状态与开工边界

**目录**：`064-pavement-roadbed-handover` | **日期**：2026-09-24 | **规格**：[spec.md](./spec.md)  
**实际分支**：`codex/road-pavement-engineering`（setup-plan返回分支为空，已用git只读核对）。

## 概要

在现有施工段参数中明确移交状态与说明，复用版本化保存，不新建数据库表。按三态筛选本次任务范围，对纳入的每项施工和配套任务施加路床日期下限，任务及结果显式列出待定段。当前25段以一次新版本升级为18段指定日期、3段已移交、4段待定。

## 技术上下文

- 语言/依赖：沿用Python、TypeScript、FastAPI/Pydantic、React19、Vite6、OR-Tools；版本以现有虚拟环境及package.json为准，不升级依赖。
- 存储：`.local-data/state/project-master.db` 的版本化参数；`.local-data/state/scheduler-config.json` 只更新主数据引用，不覆盖配置。
- 测试：pytest、Node test、tsc/Vite build、真实HTTP和浏览器核对。
- 平台：Windows本地后端8000提供前端静态文件；不新增后台服务。
- 范围：主数据编辑/导入/适配，路面生成和直接求解校验，任务与结果范围展示。
- 性能：25段100层无新增网络遍历；现有求解时间限制保持。不引入额外优化目标。
- 约束：保护现有未提交改动；历史版本只读；不填假日期，不以停用结构层代替路床待定。

## 生命周期归属

规格归属见[spec.md](./spec.md)；实现限于现有04-demo源码、邻近测试和明确列出的一个移交编辑组件。迁移临时文件归`.local-data/tmp/`，正式当前数据仍归既有state目录。

## Constitution检查

设计前、设计后均已核对：业务三态明确，日期为自然日硬边界；范围排除可见；无新增目标或资源假设；共享字段、兼容、错误码、失效与验证已定义；通过旧版本和导出备份保留数据。不存在需要豁免的宪章违反项。实施须由用户确认tasks.md。

## 设计决策

### D1：明确状态，复用主数据版本

新增施工段参数`roadbed_handover_status`、`roadbed_handover_note`，复用`roadbed_available_date`。类型和组合校验见[data-model.md](./data-model.md)。`project_master/validation.py`提供唯一后端解析规则，被主数据校验、投影、生成及求解校验复用，禁止分支各自扫描备注。

用同一版本下的`PUT .../pavement-sections/{section_id}/handover`保存单段状态；复用`_current_pavement_snapshot`和`_save_pavement_snapshot`的并发及新版本机制。Excel新增可选参数列，旧模板仍可读，旧日期按原意解释。

### D2：区分状态与真实输入错误

`handed_over`无日期合法；`pending`不产生阻断其他段的缺移交日期错误。`dated`缺日期、非法状态/日期、身份及引用错误继续阻断。待定段的未填执行参数无需为本次排程补齐，错误的对象身份与字段格式仍检查。旧记录无状态无日期保守归待定，显示说明，绝不默认为已移交。

### D3：资格筛选及硬边界

先按施工段三态划分纳入范围，保持待定段的主数据与保存配置。只为纳入段生成核心层和配套作业；跨段固定顺序仅保留纳入任务的相对次序。关系/配套引用检查仍基于完整主数据，不能将合法待定对象判为删除。

对每个纳入任务施加`earliest_start_offset`：指定日期为`max(0,移交日-计划开始日)`，已移交为0，叠加原有验收/配套日期边界。配套任务也携带同段移交状态。直接`/api/solve`不能只信传入constraints，路面校验和建模按状态再次检查日期边界，待定任务拒绝进入求解。

全部待定时在业务层短路，复用`MODEL_INVALID`状态并返回`PAVEMENT_NO_SCHEDULABLE_SECTION`，界面显示“暂无可开工施工段”，不运行空模型。空主数据仍使用原空态错误，不能冒充待定。

### D4：显式结果范围

定义`PavementHandoverScope`，在路面`ScheduleInput.pavement_handover_scope`传递；桥梁省略。生成响应的`source_summary.pavement_handover`和求解响应的`stats.pavement_handover`使用同一结构。结果成功、失败、全部待定均保留范围，待定段不获得任务日期或资源。

任务视图显示纳入段/层和待定原因。结果有待定段时明确“本次纳入范围”，不宣称全项目完成。所有任务的工期、原FS/SS/FF/SF、养生、机组容量、转场与目标保持现有实现。

### D5：单段维护与失效

主数据在既有分段下提供三态选择、日期及说明的简洁编辑；切换为非指定日期时清空当前有效日期字段，原历史版本不改写。独立组件复用现有保存与`onVersionSaved`回调。工艺逻辑页面按三态解释路床可用条件。保存成功同步当前版本并使派生任务和结果失效；失败保留草稿和原版本。

### D6：一次性升级当前客户数据

实施时先核对实时版本和25段身份，与用户源表逐项对应，不仅凭行号执行。18个日期段→dated，第7/10/19段→handed_over，第5/11/15/25段→pending；保留原因和原备注。使用既有导入预览及确认接口创建新版本，保存历史快照。比较升级前后除移交字段/来源元数据外的全部业务字段，更新配置版本引用时保护工效、资源、关系与计划开始日。应用启动不自动迁移任意其他项目。

## 项目结构与准确实施路径

以下路径均相对仓库根目录：

- 后端契约：`04-demo/backend/app/contracts/pavement.py`、`contracts/project_master.py`、`contracts/_models.py`、`contracts/__init__.py`。
- 主数据：`04-demo/backend/app/project_master/definitions.py`、`workbook.py`、`validation.py`、`service.py`、`scheduling_adapter.py`；`04-demo/backend/app/api/routers/project_master.py`。
- 排程：`04-demo/backend/app/scheduling/generation/pavement.py`、`application/pavement.py`、`solver/strategies/pavement.py`；`04-demo/backend/app/api/routers/scheduling.py`。
- 前端类型/数据：`04-demo/frontend/src/contracts/pavement.ts`、`projectMaster.ts`、`scheduler.ts`、`index.ts`；`04-demo/frontend/src/api/projectMasterApi.ts`；`04-demo/frontend/src/domain/pavement.ts`。
- 前端界面：`04-demo/frontend/src/features/projectMasterData/PavementMasterTable.tsx`、新增`PavementSectionHandover.tsx`、`styles.css`；`04-demo/frontend/src/features/logic/LogicTab.tsx`、`features/taskView/TaskViewWorkspace.tsx`、`features/scheduleResults/ScheduleResultsWorkspace.tsx`、`features/scheduleResults/presenter.ts`。
- 后端测试：`04-demo/backend/tests/test_pavement_master.py`、`test_pavement_api.py`、`test_pavement_generation.py`、`test_pavement_solver.py`、`test_pavement_contracts.py`。
- 前端测试：`04-demo/frontend/tests/pavementMaster.test.mjs`、`pavementWorkflow.test.mjs`、`pavementResults.test.mjs`、`contractsCompatibility.test.mjs`。
- 契约验证：`04-demo/tools/demo-api-mirror/api.mts`（核对路面仍显式拒绝，不改成桥梁回退）；`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`和`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`仅更新本次可解释的共享契约差异。
- 文档：本目录、`03-requirements/specs/README.md`；旧063规格的日期必填行为由本规格明确限定覆盖，旧实施证据不改写。

## 研究及产物

[research.md](./research.md)、[data-model.md](./data-model.md)、[接口契约](./contracts/roadbed-handover.md)、[quickstart.md](./quickstart.md)、[tasks.md](./tasks.md)。

仓库不存在`update-agent-context.ps1`，已按脚本目录检索确认；不创建替代脚本或改写AGENTS.md。无新增技术栈，且agent.md仅描述已实现事实，本阶段不向其中写入尚未实现的行为。该工具缺失不影响需求、设计和任务生成。
