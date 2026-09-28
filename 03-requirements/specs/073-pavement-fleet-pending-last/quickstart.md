# 验证指南

前提：仓库已有 `.venv` 与前端依赖，沿用配置，不安装/升级。实施后在仓库根目录执行一次相关验证批次。

## 核心样例

2027-04-20 起排，正常段 A：R1 水稳 1 天 → 养生 7 天 → R2 沥青 1 天。待移交段 B：R1 碎石 1 天，R1 转场 1 天。

- 初解应允许 B 在 04-22 施工，A 沥青 04-28；CP-SAT 用 B 固定在 04-22 的样例证明可行，不依赖等优方案的任意排布。
- 所有机组路线均不能出现 pending → normal；同机组养生间隙不可插入待移交后再做正常。
- 覆盖同类型两套实例、全待移交、无待移交、无正常任务的机组、固定顺序冲突、跨机组真实前置和兼容的无主机组任务。

## 命令

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_stream.py -q
node --test 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementTaskPreview.test.mjs 04-demo/frontend/tests/pavementLiveSolve.test.mjs
npm run build
.\.venv\Scripts\python.exe 04-demo/backend/scripts/capture_architecture_baseline.py --check 04-demo/backend/tests/fixtures/architecture/backend-baseline.json
node 04-demo/frontend/scripts/captureArchitectureBaseline.mjs --check 04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_docs.py
```

共享枚举的架构快照仅在审阅实际变化后按原有捕获脚本更新；不得借更新快照吞掉无关变化或已知失败。

## 结果检查

- 新输入、初解、流式及最终结果均为 `per_fleet_last`，旧标识输入有重新生成诊断；历史结果说明正确。
- 无可行解、未证明最优和中断提示保留；无伪造日期；镜像能力边界不变。
- 使用内存合成输入证明规则，不对用户页面自动发起求解；如需真实主数据补充验证，只读加载后在隔离内存计算，不保存到页面/主数据，沿用有限预算。
- 对比主数据及持久配置内容，确认未被修改。后台服务如需重载，仅按 `04-demo/runtime/README.md` 管理精确进程，不批量结束无关进程。
