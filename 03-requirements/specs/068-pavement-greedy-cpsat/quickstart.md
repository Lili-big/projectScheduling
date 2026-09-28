# 验证指南

本文件供实施阶段执行。规划阶段不启动服务、不运行求解、不改客户状态。

## 环境与输入

仓库根目录D:/codex_workspace/基建版本，使用现有.venv/Scripts/python.exe及npm.cmd；后台服务按04-demo/runtime/README.md。准备全部测试用例后再运行相关批次，新增行为先证实旧代码缺失。依赖仍为项目现有安装，不安装新包。

## 自动化批次

~~~powershell
.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_generation.py -q
node --test --test-concurrency=1 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs
npm.cmd run build
~~~

前端沿用现有Node测试与测试文件内TypeScript转换，不增加新的测试依赖。

必须覆盖：
1. 三策略确定性、完整任务、独立多机组、共享机组、配套任务、转场只计实际相邻。
2. FS/SS/FF/SF（含后序早于前序开始的合法跨机组情况）、验收日期、固定顺序/开始/资源、硬里程碑、无末尾养生。
3. 18有日期+3已移交+4待定的完整输入；pending禁止填养生空档、全pending/无pending、范围筛选和停用层。
4. 初解合法+优化UNKNOWN的真实回退序列化；无初解+CP-SAT成功/UNKNOWN/INFEASIBLE；预算耗尽不以0传入solver；矛盾结果报内部错误。
5. 16→13天确定样例，用受控合法种子验证CP-SAT能变更路线；同工期不退化，OPTIMAL只在证明一致时出现。
6. 参数缺项与旧输入保持诊断；不能吞掉错误、回写真实移交日期或改变客户机组。
7. 两条API入口、前后端新字段往返、历史缺字段、桥梁响应不增加路面数据、演示镜像仍拒绝路面、输入改动结果失效。

预算/状态分支采用可控时钟或最小可替换求解边界，避免靠极短真实时限写不稳定测试；真实CP-SAT小样例另验证模型/提示，没有mock替代全部算法验收。

## 真实规模与页面

- 只读加载实施时当前确认主数据与已保存路面配置，记录版本/指纹及是否仍为25段100任务、共享1套、跨段1天、FS0/7/7、15秒。
- 对同一快照预热后执行3次“仅初解构造＋校验”，记录每次耗时/初解工期/策略/候选数，验收每次<=1秒。不改项目正式配置，不把合成数据写入数据库。
- 执行1次完整混合求解，记录各阶段耗时、真实CP状态、初步与最终工期和最终来源；15秒配置下混合计算<=17秒。最终计划通过独立数值检查。
- 如果客户配置自规划后有变化，不恢复旧值；当前配置另记录，100任务性能可用保持原口径的非持久测试fixture验收，明确区分。
- 构建/服务更新遵循runtime手册；浏览器核对任务完整、来源/改善、4段条件日期及UNKNOWN优化回退。保留用户未保存草稿，采用独立验证页。
- 输入/配置前后做只读指纹比较；运行真实试算不自动保存或更新主数据。

## 资产及共享契约检查

~~~powershell
.venv/Scripts/python.exe 00-governance/repository-tools/validate_docs.py
.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py
.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py
.venv/Scripts/python.exe 04-demo/backend/scripts/capture_architecture_baseline.py --check 04-demo/backend/tests/fixtures/architecture/backend-baseline.json
node 04-demo/frontend/scripts/captureArchitectureBaseline.mjs --check 04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json
~~~

只更新068引入的共享字段差异，不覆盖既有无关漂移。将命令、退出结果、性能/工期实测和未覆盖风险写入tasks.md；核心要求不满足不能标完成。规划阶段仅运行资产校验器，算法验证留到用户确认实施后。
