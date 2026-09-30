# 验证指南

## 前提

在仓库根目录使用现有 .venv 与 Node/npm；后端服务、日志按 `04-demo/runtime/README.md`。已有服务可复用；需要载入后端代码时只重启已确认的本项目服务。不得启动旧不限时搜索，不修改保存配置，不刷新用户原结果页面。

## 自动验证

相关后端测试仅运行一批：

```powershell
.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_stream.py 04-demo/backend/tests/test_pavement_hybrid.py -q
```

前端请求、状态验证及构建：

```powershell
node --test 04-demo/frontend/tests/pavementLiveSolve.test.mjs
npm run build
```

契约字段更新后使用既有 capture 脚本生成必要快照，检查差异仅涵盖本次可选字段及相关签名，再对更新后的契约运行 check；相关说明参见 plan.md。不运行无关全套验证。

## 临时页面验收

1. 新开临时路面页面进入模拟求解，初值 15；输入 30、60，均不回退或截断成 15。
2. 小型合法方案普通求解按 15 秒预算执行；可提前返回。确认启动提示及结果预算均为 15。
3. 将时限改为 30，原结果仍可用；点击“优化窝工”，请求独立预算为 30，基准身份保持，启动和最终预算均为 30，工期 ≤ 基准且窝工不增。
4. 再改变时限可继续优化；计算中禁止改时限或重复启动。真实业务变更仍使基准过期。
5. 空、0、负数显示错误并禁用求解；恢复 15 后恢复可操作性。原结果保留。
6. 断线或失败保留最后合法方案并标明未完成；不要求每次一定改善，不把耗尽预算等同最优证明。
7. 不点保存配置；关闭临时页，原用户页和主数据保持。

15/30/60 的传递与实际有效截止时间用小模型及测试替身验证，无需反复把每个预算耗满。若具体页面缺少合法资源，报告数据条件，不修改数量凑出可行解。
