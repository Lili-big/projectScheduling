# 最小验收指南

本文件为实施后的验证入口，不代表当前已实现。所有命令在仓库根运行，使用已有虚拟环境和依赖。后台服务只按`04-demo/runtime/README.md`复用或启动，不能恢复旧不限时试算。

## 1. 相关自动验证

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_stream.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_solver.py -q
node --test --test-concurrency=1 04-demo/frontend/tests/pavementLiveSolve.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs
npm run build
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py
```

检查：worker低核适配/use_lns、剩余预算与非有限输入、贪心首解/冷启动、严格改善/等值保留、回调候选校验、正常最终不反退、最优证明、UNKNOWN/INFEASIBLE/一致性错误；流事件顺序、固定容量邮箱、断连停止与竞态；客户端UTF-8分块/半行/EOF/重复终态、token/fingerprint防过期、历史和同步兼容、镜像拒绝。

使用受控事件覆盖序列和计数，避免将多线程性能波动写成稳定单元测试断言。068的小样例16→13可验证真实改善及最终OPTIMAL；不是所有样例必须证明最优。

## 2. 真实100任务限时验证

只读输入：`.local-data/logs/20260926-225248-unlimited-pavement/schedule-input.json`，原SHA256为`83d619b0f18809779aa3f984e2c5eb26741d4f301037bc4d06e41f115524616b`。使用内存副本设置15秒，不覆写源文件。保持100任务、1共享机组、工效、转场、依赖、待移交和原模型。

调用同一混合入口，记录计算开始、初解、每个合法改善与结束时刻、各阶段秒数、worker配置、LNS开启、initial/final/improvement与status。每个候选走独立硬约束校验。预期初解324、正常结果不差于324；本机至少一次优于324，计算总计<=17秒。不将310或OPTIMAL列为硬门槛，不为通过重复加大预算；未改善时先诊断并报告。

开启诊断搜索日志核对组合搜索含内置LNS，将新证据保存在新的`.local-data/logs/<本次时间>/`，不覆盖旧诊断文件。不开第二份并行性能试算。

## 3. 真实HTTP与页面

复用运行中的服务与现有客户场景/范围，向新POST接口发起一次15秒求解；用支持流式逐块读取的HTTP客户端记录每个JSON行的接收时间（不得以一次性response.json或TestClient缓冲结果代替）。核对started、首个solution、可能的改善、complete顺序；首个方案先于complete，计算启动后2秒内可读到初解，另列主数据加载耗时。

页面按固定机组求解：结束前显示“正在优化/当前最好”、完整任务及条件日期，结束后显示最终与是否证明最优。网络慢或中断时保留最后已收到方案并提示未完成；运行期间改变输入/范围后，旧事件不刷新当前计划，新操作只对应一个请求。关闭连接后读取本次请求的诊断，确认StopSearch与工作线程收尾，无无限后台计算。

相同输入再经同步接口返回一次最终结果，核对字段语义与合法性，不要求多线程两次路线/工期完全一致。对用户配置、主数据以及源输入核对无写入；不自动保存页面临时改动。

## 4. 完成证据

在tasks记录命令、退出码、初解/最终工期、改善、真实阶段耗时、首包时间和线程释放证据。仅修复本次相关问题；既有仓库基线问题独立列出，不扩大本轮变更。
