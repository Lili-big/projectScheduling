# Quickstart：移除资源共享模式

## 前置条件

- 在仓库根目录执行命令。
- 使用仓库当前 Python、Node.js 与 npm 环境。
- 测试必须使用临时配置路径，不直接修改用户的 `.local-data/state/scheduler-config.json`。

## 场景 A：旧项目共享数据清理

构造包含一个工点独享池、一个显式 `PROJECT_SHARED` 池和一个缺失作用域的旧共享记录的临时配置。

预期：

- 加载结果只保留工点独享池；
- 临时配置文件被原子写回，`resource_pools` 中共享记录为 0；
- 非资源配置和工点独享字段完全保留；
- 第二次加载结果一致。

运行：

```powershell
python -m pytest 04-demo/backend/tests/test_local_scenario_config.py -q
```

## 场景 B：空资源配置与正常项目计算

构造仅包含共享池的旧项目，加载后得到 `resource_pools=[]`，再通过正常项目流程生成任务。

预期：

- 本地配置保存接口接受空资源数组；
- 需要资源的任务按现有结构化缺口诊断阻断；
- 当前项目生成结果中的共享候选、共享实例和共享诊断为 0；
- 原有底层显式共享输入求解测试保持通过，证明求解器能力未被删除。

运行：

```powershell
python -m pytest 04-demo/backend/tests/scheduling/test_fixed_resource_application.py 04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py -q
```

## 场景 C：前端页面与项目标准化

预期：

- 资源页没有共享池入口；
- `normalizeScenarioResourcePools` 删除共享池、保留工点池；
- 清理后的场景指纹不含共享数据；
- 保存 payload 不会重新携带共享池。

运行：

```powershell
Set-Location 04-demo/frontend
node --test tests/resourceWorkpointScope.test.mjs
npm.cmd run typecheck
npm.cmd run build
```

浏览器运行时用例只在静态/领域测试无法覆盖真实保存 payload 时运行一次：

```powershell
Set-Location 04-demo/frontend
node --test tests/resourceWorkpointRuntime.test.mjs
```

## 场景 D：参考镜像与文档

运行：

```powershell
node 04-demo/tools/demo-api-mirror/verify.mjs
python 00-governance/repository-tools/validate_docs.py
```

预期：参考镜像校验通过；049 文档无占位符、路径和格式错误。
