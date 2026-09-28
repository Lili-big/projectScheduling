# 验证指南

使用已有 `.venv` 和前端依赖，不升级。用户确认 tasks 后执行相关验证批次。

## 核心可复现场景

1. spec 的 R1 A[0,2)、B[6,8)，R2 C[0,10)；B/C固定，转场0。基准 D=10、I=4；应找到 I=0、工期≤10 的合法解。
2. 固定 A 或增加4天强制等待后，不得消除必要空档；跨位置转场1天按实扣除而不能虚增。
3. 当前073按机组后置和原日期/养生/互斥/硬里程碑测试保持通过；两同类资源实例独立、空资源/单任务/无主机组兼容任务口径正确。
4. 基准合法但极小预算、未改善、取消、异常都保留合法方案；零空闲基准直接证明该目标下界，不能伪造CP-SAT执行状态。
5. 相同工期、更少空闲必须发出并接收改善；空闲增加、工期超上限、错误指纹/范围/事件次序被拒绝。工期模式仍只接受更短工期。
6. 旧结果/旧strict_last/空态/当前输入变化，确认不能误用基准；本轮最优文案只指窝工，不误判旧交付口径。

## 定义的验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_stream.py -q
node --test 04-demo/frontend/tests/pavementLiveSolve.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/pavementVisualization.test.mjs
npm run build
.\.venv\Scripts\python.exe 04-demo/backend/scripts/capture_architecture_baseline.py --check 04-demo/backend/tests/fixtures/architecture/backend-baseline.json
node 04-demo/frontend/scripts/captureArchitectureBaseline.mjs --check 04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_docs.py
```

新接口/契约通过既有脚本捕获到本地日志候选，审阅后仅更新本功能变化；不覆盖其他工作树差异。以上命令每批首次运行一次；相关失败修复后只重跑受影响检查。

## 验收记录

记录输入样例、工期上限、前后空闲/转场、硬约束数值校验、流式事件与证明范围。以测试内存场景完成API闭环，不启动用户真实方案求解或保存方案。浏览器如需验证，使用独立受控合成状态，不刷新/清空用户已有结果。

比较 project-master.db、scheduler-config.json、plan-control-store.json 的内容哈希；后台重载只按 `04-demo/runtime/README.md` 管理精确进程。结果中说明未覆盖真实项目最优保证及范围外架构/治理差异。
