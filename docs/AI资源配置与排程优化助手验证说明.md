# AI资源配置与排程优化助手验证说明

日期：2026-07-09

适用范围：AI 资源配置方案生成、三方案 CP-SAT 分步求解、逐步指标对比、独立推荐解释和本地回退验证。

## 1. Demo 闭环

1. 进入前端 Demo。
2. 导入项目数据或使用默认项目场景。
3. 打开「AI资源助手」。
4. 点击「生成三方案」，系统生成工程画像和三张资源方案卡。
5. 用户检查或调整资源数量。
6. 分别点击三张方案卡中的「求解经济方案」「求解平衡方案」「求解抢工方案」；每次只调用对应方案的 CP-SAT，并立即展示该方案结果。
7. 查看逐步补全的指标对比表、整体计划、资源利用和控制墩专项视图。
8. 三套方案都完成后，点击「生成LLM推荐」；系统基于完整结果先确定推荐结论，再生成解释。

## 2. 方案生成口径

- LLM 根据工程画像、约束提示和参考样例一次性输出经济、平衡、抢工三套资源配置。
- 原 A/B/C 数量只作为参考样例，不作为固定方案。
- 外部 LLM 未配置或调用失败时，系统使用本地回退样例生成三方案。
- 桩机按资源类型分别配置，例如旋挖钻、回旋钻、冲击钻和人工挖孔班组分别给数量。

## 3. 指标来源

| 指标 | 来源 |
| --- | --- |
| 总工期、预计完工日期、求解状态 | CP-SAT 求解结果 |
| 控制墩释放、连续梁开工、资源利用率、平均等待、最大等待 | 基于 CP-SAT 任务和资源分配结果派生 |
| 转场惩罚 | 复用现有连续性诊断，MVP 阶段为诊断口径 |
| 成本估算 | 演示默认单价估算，仅用于横向比较 |

## 4. 推荐解释边界

- 推荐结论先由系统基于求解指标和轻量规则确定。
- AI 只解释推荐证据、风险和边际收益。
- 外部大模型不得改写 `recommended_scenario_id`。
- 无可比较可行结果时不输出推荐方案。

## 5. 本地配置

复制 `.local.env.example` 为 `.local.env` 后，优先配置统一的 `PROCESS_NL_LLM_*`。AI 资源助手默认复用这套配置，不需要再复制一份模型参数。

```text
PROCESS_NL_LLM_PROVIDER=openai_compatible
PROCESS_NL_LLM_ENDPOINT=https://api.example.com/v1/chat/completions
PROCESS_NL_LLM_MODEL=your-model
PROCESS_NL_LLM_API_KEY=
PROCESS_NL_LLM_TEMPERATURE=0
PROCESS_NL_LLM_RESPONSE_FORMAT=json_object
```

默认 `local` 可完成完整演示闭环，不需要真实密钥。

如 AI 资源助手确需使用不同模型，可再单独填写 `AI_RESOURCE_ASSISTANT_*` 覆盖项；留空时继续复用 `PROCESS_NL_LLM_*`。

## 6. 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_resource_scheduling_assistant.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
npm.cmd run build
```

通过标准：

- 三方案生成、资源调整、单方案求解、逐步指标对比和独立推荐解释可形成闭环。
- 单方案求解请求不调用推荐解释；只有用户点击「生成LLM推荐」才调用外部模型或本地解释。
- 不可行、未知、失效和 LLM 失败均有明确状态。
- 演示成本和转场惩罚均标识来源，不进入 CP-SAT 硬约束。
