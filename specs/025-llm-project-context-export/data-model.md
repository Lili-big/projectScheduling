# 数据模型：三方案生成前 LLM 项目信息下载

## LLMGenerationContext

一次三方案初始化中实际提供给三方案生成函数的精简项目上下文。

| 字段 | 类型 | 说明 | 校验规则 |
| --- | --- | --- | --- |
| `project_profile` | 对象 | 当前工程画像，包括项目统计、控制墩、连续梁、关键线路候选和数据质量信息 | 必须与本次初始化使用的工程画像一致 |
| `resource_types` | 对象数组 | 当前项目允许配置的资源类型及任务需求统计 | 必须来自工程画像中的资源类型 |
| `constraint_hints` | 字符串数组 | 三方案生成需考虑的约束提示 | 必须来自工程画像中的约束提示 |
| `reference_examples` | 对象数组 | 经济、平衡、抢工参考投入梯度 | 每项必须标记为非硬约束 |
| `current_resource_pools` | 对象数组 | 当前项目资源池配置 | 必须来自本次请求场景 |
| `rules` | 字符串数组 | 三方案输出边界规则 | 与当前生成逻辑保持一致 |

### 安全约束

- 不允许包含 API Key、Authorization、Endpoint、模型名称、Provider 环境变量或完整请求头。
- 不允许附带 system instruction、任务标识或输出 Schema。

## ResourceAssistantInitialResponse 扩展

| 字段 | 类型 | 生命周期 |
| --- | --- | --- |
| `llm_generation_context` | `LLMGenerationContext` | 每次初始化重新生成；随响应返回；不持久化 |

该字段与 `project_profile`、`resource_plans`、`plan_generation` 等现有字段并列。旧字段语义不变。

## LLMContextDownloadState

前端页面会话中的临时下载状态。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `context` | `LLMGenerationContext` | 直接取自最近一次成功初始化响应 |
| `generated_at` | 时间 | 响应成功时刻，用于文件名 |
| `object_url` | 临时 URL | 由 JSON Blob 创建，仅当前页面会话有效 |
| `file_name` | 字符串 | 清洗后的项目名 + 固定标识 +时间戳 |

### 状态转换

```text
无下载状态
  -> 开始生成：保持无下载状态或清除旧状态
  -> 初始化成功：建立最新下载状态
  -> 再次生成：清除旧状态，成功后建立新状态
  -> 场景变化：清除状态
  -> 初始化失败：保持无下载状态
  -> 组件卸载：回收临时 URL
```
