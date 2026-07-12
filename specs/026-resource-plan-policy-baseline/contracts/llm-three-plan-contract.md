# 契约：LLM 三方案生成与校验

## 调用输入

继续使用现有 `context` 六分区，并在现有 `rules` / `reference_examples` 范围内加入：

- 资源工作量状态与确定性三方案基线。
- 零工作量和禁用资源必须为 0。
- 只允许当前资源池中的类型。
- 数量不得超过原始上限。
- 经济、平衡、抢工同类资源数量保持非递减。
- 不输出或决定最终推荐方案。

## 首次输出

必须返回恰好三个方案，分别为 `economy`、`balanced`、`crash`：

```json
{
  "plans": [
    {
      "profile": "economy",
      "positioning": "string",
      "resource_quantities": {"resource_type": 0},
      "organization_strategy": "string",
      "generation_rationale": ["string"],
      "applicable_scenarios": ["string"],
      "expected_risks": ["string"]
    }
  ]
}
```

## 纠错重试输入

复用原始上下文与同一输出 Schema，额外提供 `validation_errors`，每项包含 `code`、`profile`、`resource_type`、`actual`、`expected`。只允许一次纠错重试。

## 后端验收

- 方案数量和标识完整、唯一。
- 字段类型符合现有 Schema，`organization_strategy` 为字符串。
- 资源类型全部已知，数量为非负整数。
- 零工作量、禁用和异常资源数量为 0。
- 不超过原始 `max_quantity`。
- 有效资源满足三方案单调性和专项边界。
- 未出现求解前最终推荐。

任何一项不满足时，首次输出进入纠错重试；重试输出不满足时使用确定性基线。

## 接口兼容性

- `ResourceAssistantInitialResponse` 外形不变。
- `llm_generation_context` 继续表示本次实际准备给 LLM 的项目上下文，下载功能不变。
- 三版方案字段不变，前端无需新增类型或组件。
