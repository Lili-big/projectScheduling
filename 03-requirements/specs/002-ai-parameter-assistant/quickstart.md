# 快速验证：AI 参数输入助手

## 前置条件

- 后端和前端依赖已按项目现有方式安装。
- 如验证真实 AI 解析，后端已配置可用 AI 服务和必要密钥，并通过后端 AI adapter 调用。
- 如验证本地确定性流程，可使用固定 fixture 或 mock AI 响应；mock 只能用于测试和本地验证，不能替代正式解析主路径。
- 当前阶段为规划验证说明，不代表功能已经实现。

## 建议验证命令

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

前端构建：

```powershell
npm --prefix frontend run build
```

如果 PowerShell 执行策略阻止 `npm`，使用：

```powershell
npm.cmd --prefix frontend run build
```

## 验证场景 1：多资料解析但不修改方案

1. 准备包含工效、资源数量和里程碑的文本、Word、Excel、PDF 和图片资料。
2. 上传资料并点击解析。
3. 检查返回建议按类别分组展示。
4. 检查当前 `ScenarioInput` 在点击应用前没有变化。

通过标准：

- 解析接口返回 `suggestions`、`material_summaries` 和来源证据。
- 页面可展示资料级失败，不影响其他资料建议。
- 未点击应用前，工艺、资源和里程碑配置不变。

## 验证场景 2：置信度和默认勾选

1. 使用 fixture 生成 `High`、`Medium`、`Low` 三类建议。
2. 打开建议审阅面板。
3. 检查默认勾选状态。

通过标准：

- `High`、无冲突、字段完整建议可以默认勾选。
- `Medium` 不默认勾选。
- `Low` 进入待人工完善。
- 每条建议展示等级和 0-100 分。

## 验证场景 3：冲突处理

1. 准备两份资料，对同一资源数量或同一工效给出不同值。
2. 解析后查看冲突组。
3. 尝试不解决冲突直接应用。
4. 选择一个候选值或手动填写后再应用。

通过标准：

- 系统展示当前值、候选值和来源。
- 未解决冲突时应用按钮不可用或接口返回 400。
- 解决冲突后只应用用户选择或手填的值。

## 验证场景 4：局部应用和当前方案边界

1. 选择部分高置信建议。
2. 保留其他建议不选。
3. 点击应用。
4. 检查项目级配置或默认配置未保存。

通过标准：

- 仅选中建议更新当前 `ScenarioInput`。
- 未选中建议保持不变。
- 不触发本地项目配置保存。
- 页面显示应用摘要。

## 验证场景 5：里程碑默认规则

1. 准备只写日期和节点名称的里程碑资料。
2. 准备包含“合同节点”“控制性节点”“必须完成”等语义的资料。
3. 分别解析并检查建议类型。

通过标准：

- 无明确约束类型的里程碑默认为内部软里程碑。
- 明确合同或控制性语义的里程碑才建议硬约束或控制性类型。
- 用户仍可在应用前调整。

## 验证场景 6：上传限制和服务失败

1. 上传超过 10 个文件。
2. 上传总大小超过 50MB 的文件组合。
3. 模拟 AI 服务超时或不可用。

通过标准：

- 超限请求返回明确错误。
- AI 服务失败时当前方案不变。
- 页面能说明失败原因并允许用户重试或减少资料。

## 验证场景 7：不持久化原文件

1. 完成一次解析和应用。
2. 检查后端只保留建议、来源摘要和应用结果所需信息。
3. 检查没有长期保存上传原文件。

通过标准：

- 应用请求和响应不依赖原文件再次读取。
- 可追溯信息来自短摘要、来源位置和应用明细。

## 验证场景 8：图片资料低置信流程

1. 上传资源计划截图或里程碑截图。
2. 查看图片来源建议。
3. 手动确认或补充低置信建议。

通过标准：

- 图片识别不清时建议为 `Low` 或待人工完善。
- 来源证据说明图片区域或识别依据。
- 用户确认后可局部应用有效值。

## 验证场景 9：20 条建议批次审阅

1. 使用包含至少 20 条建议的 fixture，其中覆盖工效、资源、里程碑、高置信、低置信和冲突项。
2. 运行解析并打开审阅面板。
3. 批量选择其中一部分建议并应用。

通过标准：

- 页面能一次展示至少 20 条建议，无需用户逐个打开来源文件。
- 每条建议仍能看到来源摘要、置信度和当前状态。
- 仅用户选择且冲突已解决的建议会被应用。

## 验证场景 10：结构参数替换被排除

1. 上传包含桥梁跨径、墩台、桩基数量等结构参数替换意图的资料。
2. 同时包含可用于定位工艺、资源或里程碑的结构描述。
3. 运行解析并查看建议。

通过标准：

- 系统不得生成替换项目结构参数的建议。
- 结构信息只能作为工艺工效、资源或里程碑目标定位依据。
- 当前项目结构配置保持不变。

## 验证场景 11：短期 suggestion store 过期

1. 完成一次解析并获得 `run_id`。
2. 模拟该 `run_id` 过期或不存在。
3. 使用该 `run_id` 调用应用接口。

通过标准：

- 应用接口返回过期或不存在提示。
- 当前 `ScenarioInput` 不发生变化。
- 页面提示用户重新解析或重新上传资料。

## 完成证据

进入实现后，任务完成应至少提供：

- 后端测试通过结果。
- 前端构建通过结果。
- 一组文本/表格/PDF/图片 fixture 的解析摘要。
- 至少 20 条建议批次审阅和局部应用验证说明。
- 结构参数替换被排除的负向验证说明。
- 短期 suggestion store 的过期或不存在验证说明。
- 应用后旧任务视图和求解结果过期的验证说明。
- 未覆盖场景和降级策略说明。

## 最终实现补充

- 后端 fixture：`backend/tests/fixtures/ai_parameter_assistant_cases.json`。
- 关键后端验证：`backend/tests/test_ai_parameter_assistant_parse.py`、`test_ai_parameter_assistant_limits.py`、`test_ai_parameter_assistant_review.py`、`test_ai_parameter_assistant_conflicts.py`、`test_ai_parameter_assistant_apply.py`、`test_ai_parameter_assistant_apply_failures.py`、`test_ai_parameter_suggestion_store.py`、`test_ai_parameter_assistant_candidates.py`、`test_ai_parameter_assistant_images.py`、`test_ai_parameter_assistant_scope.py`、`test_ai_parameter_ai_client.py`。
- AI adapter 配置：默认 `AI_PARAMETER_ASSISTANT_PROVIDER=local` 使用本地启发式适配器；正式 HTTP/OpenAI-compatible 调用通过 `AI_PARAMETER_ASSISTANT_ENDPOINT`、`AI_PARAMETER_ASSISTANT_API_KEY`、`AI_PARAMETER_ASSISTANT_MODEL`、`AI_PARAMETER_ASSISTANT_RESPONSE_FORMAT` 和 `AI_PARAMETER_ASSISTANT_TIMEOUT_SECONDS` 配置。
- 短期 store：默认 TTL 为 60 分钟，可用 `AI_PARAMETER_ASSISTANT_STORE_TTL_MINUTES` 调整；应用接口只依赖 `run_id` 和 store 中的结构化建议，不重新读取原文件。
- Netlify 降级：`/api/ai-parameter-assistant/parse` 和 `/api/ai-parameter-assistant/apply` 在 Netlify 演示函数中返回 `AI_PARAMETER_ASSISTANT_FASTAPI_REQUIRED`，提示连接 FastAPI 后端。
- 前端入口：`frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx`，解析只展示建议，应用才更新当前方案并清空旧任务视图、求解结果和方案对比。
