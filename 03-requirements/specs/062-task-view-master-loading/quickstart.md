# 快速验收：任务视图权威主数据快速加载

## 前置条件

- 按 `04-demo/runtime/README.md` 启动 FastAPI 与 Vite。
- 当前 Demo 场景关联已确认的项目主数据版本。
- 性能验收使用仓库现有 13 工点、1586 任务运行基线。

## 场景 1：批量接口最小且完整

向 `POST /api/project-master/versions/{version_id}/task-view-display-map` 发送重复、乱序的两个合法工点 ID。

预期：

- 200，返回两个去重工点且顺序稳定；
- 版本 ID 与路径一致；
- 工点及工区名称可构建任务视图映射；
- 响应中不存在 `components`、`parameters` 和 `source`。

再分别验证空集合、缺失工点、缺失版本和超过 500 项，预期遵循共享契约且不返回部分成功。

## 场景 2：原子展示与失败重试

打开任务视图并暂停批量映射响应。

预期页面保持“正在加载权威项目主数据”，任务行和原始 ID 均不出现。恢复成功响应后，完整任务 DOM 只提交一次。

令首次批量请求失败，预期显示通用错误和重试按钮；点击重试并成功后一次性展示完整权威名称。

## 场景 3：版本和集合切换

在旧批量请求未完成时切换主数据版本或规范化工点集合，使新请求先返回、旧请求后返回。

预期最终只显示新身份映射；旧响应覆盖次数、部分映射提交次数和原始 ID 冒充名称次数均为 0。

## 场景 4：性能验收

在服务已启动的同一环境连续执行 3 次硬刷新。

每次预期：

- 权威显示映射业务请求数不超过 1；
- 从映射加载开始到 1586 条权威任务 DOM 就绪不超过 5 秒；
- 响应体不超过 442 KB（既有 2.21 MB 的 20%）；
- 任务名称 DOM 提交一次；原始 ID/章节代码/占位符冒充最终名称均为 0。

## 定向验证命令

```powershell
python -m pytest 04-demo/backend/tests/test_project_master_version_api.py 04-demo/backend/tests/test_contracts_project_master.py
node --test 04-demo/frontend/tests/taskViewProjectMasterDisplay.test.mjs 04-demo/frontend/tests/taskView.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs
npm.cmd --prefix 04-demo/frontend run build
npm.cmd --prefix 04-demo/frontend run test:task-view-runtime
python 00-governance/repository-tools/validate_docs.py
git diff --check -- 03-requirements/specs/062-task-view-master-loading 04-demo/backend 04-demo/frontend
```

运行时测试会写入 `.local-data/logs/<启动时间>/`，不纳入正式交付资产。相关失败必须修复后复验；有明确证据表明与本功能无关且不影响核心目标的问题只记录为剩余风险，不扩大修改范围。
