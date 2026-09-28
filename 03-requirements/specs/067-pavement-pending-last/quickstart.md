# 验证指南：067待移交段后置排程

**状态**：已按确认任务完成相关验收，实测结果及例外见[tasks.md](./tasks.md)。

## 自动化批次

仓库根目录`D:\codex_workspace\基建版本`。先写新验收用例并确认现状缺失/失败；实现后运行一次相关完整批次，有新修改或失败修复才重跑受影响部分。

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_master.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_api.py -q
Push-Location 04-demo/frontend
node --test --test-concurrency=1 tests/contractsCompatibility.test.mjs tests/pavementMaster.test.mjs tests/pavementTaskPreview.test.mjs tests/pavementWorkflow.test.mjs tests/pavementResults.test.mjs
Pop-Location
npm.cmd run build
```

build包含类型检查，不重复运行typecheck。不通过改变客户时限或资源掩盖UNKNOWN。

| 场景 | 验收点 |
|---|---|
| 混合三态 | 全部生成，pending保留事实和原因，工期/工效/FS+N不变 |
| 正常A和pending B各2天，单机组转场1天，9月23日起 | A为23—24日，25日转场，B为26—27日；需移交26日、完成27日 |
| 多机组、正常段有层间间歇 | 所有pending start >= 正常任务最大end；不得利用空闲提前开工 |
| 正工期配套任务 | 参与正常边界、pending后置及两类段级日期 |
| 全pending / 无pending | 全pending可从计划日起附条件排程；无pending原规则保持 |
| pending参数缺失、停用层或全空 | 明确缺项/空态诊断，不丢段后只排正常任务，不补假任务 |
| 直接solve无scope / 篡改scope | 前者强制后置，后者报错；dated日期下界也不可绕过 |
| 旧blocked输入 / 旧结果 | 输入要求重生成，历史不补写范围和预测日期 |
| 顺序/硬里程碑冲突 | 明确错误或INFEASIBLE，不松绑；保留合法SS/FF/SF |
| UNKNOWN等失败状态 | 有状态/原因，无推算日期，不冒用上次成功结果 |
| 状态变更、刷新、序列化导出 | 重新归组，旧输入失效；新字段保留，主数据事实不被自动修改 |
| 桥梁兼容 | 既有契约通过，缺省不增加路面字段 |

## 当前数据与页面

1. 只读记录实施时最新主数据版本、段/层/状态/备注与配置，不用规格中的V26覆盖后续用户修改。
2. 按`04-demo/runtime/README.md`更新前端构建和必要的服务重启，只操作核实的进程。
3. 浏览器应生成25段100核心任务，其中4段16任务附条件；配套任务单独计数。任务页有标识、原因；工艺逻辑不再提示待定段不排程。
4. 按现有时限/机组运行一次真实求解。可行时逐段核对后置、容量、转场、两类日期及前提。仍UNKNOWN则如实记录，不展示假日期；合成用例可证明日期表，但不得宣称客户数据已出解。
5. 刷新、通过现有结果导出/序列化路径读回，核对新字段；前后比较主数据和配置，确认真实状态/日期、层、资源未变，不保存测试用虚假移交事实。

## 文档、仓库与完成证据

新增正式文档后执行只读校验，不运行清理脚本：

```powershell
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_docs.py
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py
```

区分新增问题与既有依赖审批差异、9项历史坏引用。实施后共享契约影响架构快照时只更新067能解释的差异，不吸收无关漂移。实际测试/浏览器/客户求解状态及风险记录到tasks.md；核心约束验证未通过不得标记完成。
