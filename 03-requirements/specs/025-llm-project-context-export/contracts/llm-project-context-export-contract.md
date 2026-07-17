# 接口契约：三方案生成前 LLM 项目信息下载

## 初始化响应扩展

`POST /api/ai-resource-assistant/initialize` 的请求保持不变。

响应新增：

```json
{
  "project_profile": {},
  "resource_plans": [],
  "plan_generation": {},
  "reference_examples": [],
  "constraint_hints": [],
  "llm_config_status": {},
  "diagnostics": [],
  "llm_generation_context": {
    "project_profile": {},
    "resource_types": [],
    "constraint_hints": [],
    "reference_examples": [],
    "current_resource_pools": [],
    "rules": []
  }
}
```

## 一致性约束

- `llm_generation_context` 必须是在本次初始化中传给三方案生成函数的同一上下文值。
- 外部 LLM 成功、本地 Provider 回退、外部调用失败回退三种成功响应都必须包含该字段。
- 初始化端点返回错误响应时不承诺提供上下文，前端不得沿用旧下载状态。
- 新增字段不改变现有字段、状态码或回退行为。

## 内容约束

- 顶层字段固定为 `project_profile`、`resource_types`、`constraint_hints`、`reference_examples`、`current_resource_pools` 和 `rules`。
- 内容不得包含密钥、Authorization、Endpoint、Provider/模型配置、system instruction、`output_schema` 或完整 HTTP 请求。

## 页面契约

- 仅 AI 多方案比选主视图在初始化成功后显示下载入口。
- 链接文案为“下载本次 LLM 项目信息 JSON”。
- 下载文件使用响应字段原值，以 UTF-8、两空格缩进写为 JSON。
- 文件名格式为 `<项目名>-llm-three-plan-context-<YYYYMMDD-HHmmss>.json`；项目名中的文件名非法字符替换为短横线。
- 再次生成、场景变化、请求失败和组件卸载必须清除或回收旧下载状态。
