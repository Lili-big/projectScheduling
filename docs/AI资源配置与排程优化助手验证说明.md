# AI资源配置与排程优化助手验证说明

日期：2026-07-13

适用范围：AI 资源配置方案生成、严格固定资源单次 CP-SAT 分步求解、四种业务状态、逐步指标对比、独立推荐解释和本地回退验证。

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

### 3.1 严格固定资源求解

- 每个 AI 方案严格使用 LLM 推荐或用户调整后的 `quantity` 展开命名资源。
- 每个方案只运行一次保留现有三个目标项的完整 CP-SAT，不先运行基础排程。
- 目标延期时保留当前排程和延期信息，不进入最大资源、最少资源、资源压力搜索或候选复排。
- 人工挖孔、冲击钻、回旋钻等工艺工作量为 0 时，对应资源保持为 0，不自动补足。
- 通用「模拟求解」入口仍保留原有资源增量候选能力，不受 AI 严格规则影响。

### 3.2 四种业务状态

| 状态 | 含义 | 是否参与推荐 |
| --- | --- | --- |
| `met` | 已有可行排程且目标满足 | 是 |
| `not_met` | 已证明当前完整目标模型最优，但目标仍延期 | 否 |
| `unconfirmed` | 已有延期排程但未证明最优，或限时内未确认 | 否 |
| `infeasible` | 资源覆盖错误或已证明物理不可行 | 否 |

页面同时保留求解器状态和业务状态，不能把 `FEASIBLE + 目标延期` 表述为资源一定不足。

## 4. 推荐解释边界

- 推荐结论先由系统基于求解指标和轻量规则确定。
- AI 只解释推荐证据、风险和边际收益。
- 外部大模型不得改写 `recommended_scenario_id`。
- 只有业务状态为 `met` 的方案进入推荐候选集；没有 `met` 时不输出正式推荐方案。

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
- 每个 AI 单方案的 `solver_call_count` 为 1，`resource_expansion_attempted` 为 `false`，输入资源快照与方案数量一致。
- 单方案求解请求不调用推荐解释；只有用户点击「生成LLM推荐」才调用外部模型或本地解释。
- `met`、`not_met`、`unconfirmed`、`infeasible`、工作流失效和 LLM 失败均有明确状态。
- 演示成本和转场惩罚均标识来源，不进入 CP-SAT 硬约束。
