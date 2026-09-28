# 验证指南：跨工艺共享机组

2026-09-24已完成实施、自动验证、服务更新、客户配置回读和浏览器验收。以下场景保留为复现指南，实际证据见文末。

## 前置条件

仓库根目录、现有.venv及前端依赖。服务启停只按 `04-demo/runtime/README.md`；不得为验证填造客户路床/养生。测试场景须显式给足日期、养生、工效及转场参数。

## 最小自动验证批次

```powershell
.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_config.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_api.py -q
node --test --test-concurrency=1 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs 04-demo/frontend/tests/resourceWorkpointScope.test.mjs
npm.cmd run build
```

只在变更/失败需要时重跑相关验证；不例行执行全量套件。补充契约/工点兼容用例验证桥梁默认响应无新字段。

## 核心可复现场景

1. 两个独立段各一道1天任务，分别碎石、水稳，计划日即路床可用、末层等待0、无验收晚日期，共享资源1套、转场0：实例仅1个、分配同一资源ID、任务不重叠，objective_days=2。改为2套后objective_days=1，单任务仍1天。
2. 同例转场改1天：一套时两任务实际相邻有1天空隙，objective_days=3，只有一次真实转场；工序切换不产生另一笔时间。同段同幅串行换工艺时转场0。
3. 水稳完成后7天养生：共享实例可在养生期间执行别段碎石；工序依赖与末层可用日期仍满足。
4. 仅水稳专用1套不能做碎石；勾选碎石后可做；两种有效机组并存时均遵循能力/工点范围。直接/solve移除任务process_id或篡改资源能力到不兼容，不能绕过诊断。
5. 旧资源无新增字段保持原专用结果；空工艺旧池读取不扩大能力；新有效组清空能力保存失败；通用组未知能力拒绝。0套组转场未填不阻断已有有效组。
6. 资源名称、适用工艺、数量、转场、范围、启用变化使旧结果失效；保存刷新保持；失败保留编辑。显示数量不因选择两个工艺而翻倍。

## 客户配置与页面

自动验证通过后，重新GET当前pavement-project配置，按现有本地备份路径策略备份；只将现有水稳组扩为碎石/水稳共享。PUT前重新核对配置，变更则重读合并。GET验证稳定ID、1套、1天、双工艺及其他配置不变。

构建并按runtime说明重启有变更的后端，浏览器先检查未保存编辑，再刷新确认资源页。若客户排程仍有路床/养生缺项，记录具体诊断，不补造输入；064待确认不能算本功能失败或完成。

## 文档及仓库检查记录

2026-09-24规划批次实际记录：

- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_docs.py`：退出0，documentation links and API facts: OK (14 documents)。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py`：退出1，requirements.txt changed without architecture dependency approval。与064规划记录相同；本次未修改依赖或requirements.txt。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py`：退出1，9项missing-workpackage-reference，仍为7月客户验证材料及standalone/json-task-viewer历史输入输出，与064记录相同；不属于本功能新增目录错误。
- tasks一致性检查通过：10项、全覆盖，无实现阻塞。未运行实现测试、未改业务代码、未更新客户配置。实施证据由tasks执行后补充。

## 实施结果（2026-09-24）

- 用户已明确回复“实施”，按speckit-implement完成10项任务，064路床三态未实施。
- 测试先行：新增契约/配置3项在实现前失败（实例字段缺失、空能力保存未拒绝、旧空能力未规范化）；新增资源展开和共享求解4项在实现前失败（仍按专用机组匹配、0套仍要求转场）。修改已修复这些行为。
- 上述完整pytest命令退出0：54 passed；包含直接/solve绕过界面的能力、工点及缺少工艺ID诊断，API保存回读和失败不改文件，桥梁默认字段省略。
- 上述node:test命令初次34通过、1失败；原因是测试加载器的TypeScript默认低版本目标不能正确转译Set展开。只将该测试加载器调整到ES2022，再运行 `node --test 04-demo/frontend/tests/pavementWorkflow.test.mjs`，退出0、7 passed。相关前端35项最终全部通过，未重复其他已通过测试。
- `npm.cmd run build`退出0。Vite仍有大于500kB的chunk提示；不影响构建及本功能，不开展无关分包改造。
- 实际改动：后端Resource和PavementTaskContext契约、路面资源能力解析、配置读写校验、任务生成、直接求解匹配；前端对应类型、资源多选/新增/名称/校验及样式；相关测试。既有每实例Circuit/NoOverlap、转场约束、结果展示直接复用，未改CP-SAT目标或工效。
- 已验证原8000进程父进程1476/子进程20756命令行为本仓库uvicorn后才重启。新启动器PID31404，日志 `.local-data/logs/20260924-181601-149/`，/api/health返回ok。系统进程读操作在默认沙箱拒绝后以获准的提升权限执行；未停止无关进程。
- 更新前备份 `.local-data/state/scheduler-config.before-shared-fleets-20260924-181552.json`；重新读取并比较最新API数据后，仅通过PUT配置接口修改当前水稳池label、compatible_process_ids。API及落盘JSON逐字段比较确认其余所有字段、其他项目、主数据版本均不变。
- 当前客户池：`pavement-cement_stabilized_base-pool`，名称“碎石/水稳共享机组”，数量1、跨段转场1天，适用 `pavement-granular_base` 与 `pavement-cement_stabilized_base`。碎石/沥青原专用池仍0套。
- 浏览器8000页面验收：刷新后双工艺勾选与1套/1天可见；清空适用工艺显示错误并禁用保存；恢复双勾选、保存成功；API和落盘再次确认只有上述两个字段变化。已检查最终截图，列名、多选、数量及名称显示完整。
- 真实客户生成接口返回100个结构层任务、仅1个资源实例，无PAVEMENT_RESOURCE_MISSING或PAVEMENT_TRANSFER_UNCONFIRMED。仍有60条PAVEMENT_DATA_INCOMPLETE（原路床日期及末层等待条件缺项）；没有填造输入或声称客户完整项目已可求解。当前主数据仍为pmv-50a66eec36624a459aaf2ead8fb91142。
- 仓库级既有依赖审批提示及9项历史材料引用缺失沿用前述规划证据；本次无新增依赖，未改那些历史材料。残余风险为未完成的客户开工/养生输入及既有仓库治理问题，不影响已验证的共享机组能力。
