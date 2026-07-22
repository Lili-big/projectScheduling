# 快速验证：AI 批量初始化工点工装资源

## 1. 本地真实模型配置

复制环境模板（若尚未创建）：

```powershell
Copy-Item .local.env.example .local.env
```

只在被忽略的 `.local.env` 中填写：

```dotenv
AI_RESOURCE_ASSISTANT_PROVIDER=openai_compatible
AI_RESOURCE_ASSISTANT_ENDPOINT=https://your-provider.example/v1/chat/completions
AI_RESOURCE_ASSISTANT_MODEL=your-model
AI_RESOURCE_ASSISTANT_API_KEY=your-secret
AI_RESOURCE_ASSISTANT_TIMEOUT_SECONDS=60
AI_RESOURCE_ASSISTANT_TEMPERATURE=0
AI_RESOURCE_ASSISTANT_RESPONSE_FORMAT=json_object
```

重启后端使本地环境重新加载。不得把真实值写入 `.local.env.example`、测试或文档。

## 2. 自动验证

后端定向测试：

```powershell
python -m pytest 04-demo/backend/tests/test_ai_workpoint_resource_initializer.py 04-demo/backend/tests/test_assistant_routes.py 04-demo/backend/tests/test_contracts_assistants.py -q
```

前端定向测试、类型和构建：

```powershell
node --test 04-demo/frontend/tests/aiResourceInitialization.test.mjs 04-demo/frontend/tests/resourceWorkpointScope.test.mjs
npm.cmd run typecheck
npm.cmd run build
```

契约与文档：

```powershell
python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path(r'03-requirements/specs/059-ai-batch-resource-initialization/contracts/ai-workpoint-resource-initialization.openapi.yaml').read_text(encoding='utf-8')); print('openapi yaml ok')"
python 00-governance/repository-tools/validate_docs.py
git diff --check
```

## 3. 真实页面闭环

准备一个包含至少两个已确认桥梁工点的项目：

1. 工点 A 已配置一个本地资源，另一个候选资源缺失。
2. 工点 B 没有资源，但结构和工艺资料完整。
3. 记录点击前完整 `resource_pools` JSON。
4. 进入“资源配置”，点击“AI快速配置工装”。
5. 验证按钮进入加载状态且不能重复点击。
6. 成功后逐个切换工点，确认 A 的已有资源逐字段不变，只新增缺失资源；B 出现合法初始化资源。
7. 确认没有新增项目共享池、未知资源或 `precast_beam_team`。
8. 在某工点人工修改一个 AI 数量，点击现有“保存”。
9. 重新加载页面，确认整批新增资源和人工修改均被恢复。

## 4. 失败原子性

分别验证以下情况，前后比较完整资源 JSON，预期差异均为 0：

- provider 为 `local` 或 API Key 为空；
- endpoint 返回 401/403；
- 网络超时；
- 非 JSON 响应；
- 未知工点或未知资源类型；
- 数量为小数、负数、0 或上限小于投入；
- 部分工点合法、部分工点非法；
- 调用期间切换项目主数据版本；
- 调用期间人工修改资源配置。

## 5. 密钥检查

- 浏览器网络请求中只应看到对本地后端的初始化请求，不应看到 API Key。
- 后端响应、页面错误、测试快照和日志中不得出现真实 Key 或 Authorization。
- `git status` 不得显示 `.local.env`。

## 6. 2026-07-21 实施验证记录

- 双工点闭环：`test_ai_workpoint_resource_initializer.py` 使用两个桥梁工点、多类结构、已有本地资源和缺失候选，验证后端仅新增缺失的工点独占资源；8 项测试通过。真实 OpenAI-compatible HTTP 请求使用受控替身验证单次 JSON 请求、模型/候选上下文和响应解析，未使用本地推荐回退。
- 失败原子性：覆盖未知/缺失工点、未知/重复资源、数量 0、上限倒置、一次纠错及二次失败；现有 `resource_pools` 快照差异为 0。严格模型配置、401/403、超时、非法 JSON 和错误脱敏 7 项测试通过。
- 前端闭环：AI 按钮、重复点击门禁、项目版本/资源语义指纹、原子合并、冲突拒绝、逐工点编辑和不自动保存共 27 项定向测试通过；`npm.cmd run typecheck` 与 `npm.cmd run build` 通过。
- 契约与文档：后端架构契约 7 项通过，059 OpenAPI YAML 解析通过，文档验证通过，`git diff --check` 通过；架构基线已更新为 66 个后端 API 与 41 个前端 API 函数。
- 非本功能失败：联合运行旧 `test_ai_resource_scheduling_assistant.py` 时有 39 个既有三方案助手用例失败，主要因旧请求未提供上一功能已要求的 `target_workpoint_id`，以及旧共享/独占资源语义未同步；本次新增的严格初始化边界 7 项均通过。`apiCompatibility.test.mjs` 的旧架梁镜像 v2 断言仍失败，与 059 无关。
- 待人工验证：仓库未配置真实模型密钥，因此尚未执行第 3 节真实供应商页面闭环。用户填写 `.local.env` 并重启后端后，按第 3 节完成一次人工验证即可。
