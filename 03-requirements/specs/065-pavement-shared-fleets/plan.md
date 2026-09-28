# 实施计划：路面机组跨工艺共享

**目录**：`065-pavement-shared-fleets` | **工作分支**：`codex/road-pavement-engineering` | **日期**：2026-09-24 | **规格**：[spec.md](./spec.md)

## 概要

复用 ResourcePool.compatible_process_ids 维护适用工艺；资源实例携带同名能力字段，任务上下文携带实际 process_id。路面专用匹配改为工艺ID与工点范围匹配，同一资源实例承载跨工艺任务。复用现有 CP-SAT 命名资源路径、NoOverlap、养生及转场，不建立第二套容量。

## 技术上下文

- 语言/运行时：现有 Python venv、TypeScript；不更换版本、不引入依赖。
- 依赖：FastAPI/Pydantic、OR-Tools CP-SAT、React19/Vite6。
- 存储：现有 `.local-data/state/scheduler-config.json` 的 pavement_profiles；不变更 SQLite 主数据。
- 测试：pytest、现有 node:test、tsc/Vite构建、真实浏览器及API保存回读。
- 平台：Windows本地，8000服务构建前端；运行命令按 `04-demo/runtime/README.md`。
- 性能：沿用现有求解时间限额；同一共享实例必须只有一条跨工艺路径。增加候选任务可能增大路径图，不承诺未测耗时。
- 范围：资源编辑、共享契约、路面生成/求解、配置兼容、结果核对；桥梁无业务变化。
- 约束：不修改工效、任务工期、关系/养生、目标函数；不实现064，也不合并养生页面。

## 生命周期归属

沿用 [spec.md](./spec.md) 的生命周期归属；实现限定在以下文件：
- 后端共享契约：`04-demo/backend/app/contracts/_models.py`、`04-demo/backend/app/contracts/pavement.py`。
- 资源解析与配置：`04-demo/backend/app/scheduling/domain/resource_scope.py`、`04-demo/backend/app/local_scenario_config.py`。
- 路面：`04-demo/backend/app/scheduling/generation/pavement.py`、`04-demo/backend/app/scheduling/solver/strategies/pavement.py`；`solver/constraints/pavement.py` 复用，不预设重写。
- 前端：`04-demo/frontend/src/contracts/scheduler.ts`、`contracts/pavement.ts`、`domain/pavement.ts`、`features/resources/ResourcesTab.tsx`、`features/resources/styles.css`。
- 仅按验证需要修正已有资源名称展示：`04-demo/frontend/src/features/scheduleResults/presenter.ts`。
- 验收：后端现有 `test_pavement_contracts.py`、`test_pavement_config.py`、`test_pavement_generation.py`、`test_pavement_solver.py`、`test_pavement_api.py`；前端现有 `pavementWorkflow.test.mjs`、`pavementResults.test.mjs`、`contractsCompatibility.test.mjs`、`resourceWorkpointScope.test.mjs`。
- API沿用system/scheduling路由；演示镜像继续拒绝路面，无新路由。只在契约核对发现漏识别时修改 `04-demo/tools/demo-api-mirror/api.mts`。

## Constitution 检查

研究前：来源、范围、业务共享容量、边界和可复现验收均已明确；无阻塞澄清。
设计后：输入输出及兼容见数据模型/契约；硬约束及目标不变；客户配置只经API局部应用；不新增依赖或复制容量；阶段归属合法。用户确认tasks后才实施。无违反项。

## 实施决策

- **D1**：复用池的 compatible_process_ids，不另设第二个可编辑“能力列表”。界面按当前工艺库显示可多选工艺；精确匹配工艺ID，不靠显示名或解析ID字符串。
- **D2**：Resource 新增可选 compatible_process_ids；PavementTaskContext 新增可选 process_id。桥梁默认序列化不出现新字段；原 Task.compatible_resource_types 保留旧任务类别语义，路面显式能力匹配优先。
- **D3**：生成器通过 resolution.pools 的 effective_pool_id→source_pool_id，给已展开的实例附加适用工艺；实例数量、ID、工点范围均复用现有解析。无需修改桥梁展开逻辑。
- **D4**：旧专用池兼容读取：缺失/空工艺列表按其既有专用类型关联当前工艺库，不扩大到其他类别；新保存的有效池要求非空。新增通用机组 type=`pavement_paving_crew` 必须显式选择工艺，不做类型推断。生成接口兼容旧专用空列表；保存接口禁止有效组清空工艺。
- **D5**：路面匹配辅助函数放在既有 resource_scope.py，供生成/验证复用；显式 Resource 能力非空时精确匹配 task.pavement_context.process_id。旧Resource字段缺失可回退单一旧类型；新能力配旧缺process_id任务则提示重新生成，不能默认为任意工艺。
- **D6**：有效数量按现有作用域/覆盖规则解析；0套、停用或无可用实例不要求转场日期。非法引用、ID冲突仍诊断。无候选任务报PAVEMENT_RESOURCE_MISSING，配置非法用PAVEMENT_REFERENCE_INVALID，缺转场用PAVEMENT_TRANSFER_UNCONFIRMED。
- **D7**：求解复用 add_pavement_fleet_paths；跨工艺共享资源只建一条路径，容量按资源实例而非工艺种类计算。保持硬边界、日历天及原目标。
- **D8**：UI允许新增组、名称编辑、适用工艺多选、数量/转场/范围/启用。新组0套、转场未填，至少主动选择一种工艺才作为有效组保存；不默认赠送资源。禁用保存时所有编辑控件，失败保留输入；沿用场景指纹失效机制。
- **D9**：当前客户配置实施后重新读API，备份原配置，再更新现有水稳池能力及名称，数量1、转场1维持；碎石/沥青池仍0。写入前比较最近读取内容，若变化则重读合并；不绕过版本校验，不更新主数据或工效。
- **D10**：独立样例先证明共享排程。客户配置回读通过仅表示资源已生效；缺路床/养生等诊断原样报告，不伪称客户完整计划求解成功。

## 产物与顺序

[research.md](./research.md) → [data-model.md](./data-model.md) / [contracts/shared-fleets.md](./contracts/shared-fleets.md) / [quickstart.md](./quickstart.md) → [tasks.md](./tasks.md)。

现有脚本目录无 update-agent-context.ps1，故不执行不存在的脚本，不手工修改AGENTS。任务生成后做一次一致性检查并等待确认；064保持原待确认状态。

## 复杂度跟踪

无宪章例外；不引入机型、设备清单、复合机组或多资源联合作业模型。

