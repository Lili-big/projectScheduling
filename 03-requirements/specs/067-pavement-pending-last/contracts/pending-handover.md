# 接口契约：严格后置的待移交段

无新端点。沿用任务生成、`POST /api/solve-scenario`与`POST /api/solve`。字段定义见[数据模型](../data-model.md)。

## 范围

生成结果schedule_input.pavement_handover_scope与source_summary.pavement_handover一致。求解结果stats.pavement_handover保存本次校验后的范围。两段样例片段：

```json
{
  "total_section_count": 2,
  "included_section_count": 2,
  "included_layer_count": 2,
  "blocked_sections": [],
  "pending_policy": "strict_last",
  "pending_sections": [
    {"structure_id": "B", "section_name": "待移交段B", "reason": "征地待解决", "component_ids": ["B-L1"]}
  ]
}
```

B任务保留pending和备注，真实日期为空；工程量、工效、资源与关系仍按原契约。

## 成功日期

仅FEASIBLE/OPTIMAL的pavement_summary新增下列片段。示例来自spec合成样例，并非客户真实交付日：

```json
{
  "pending_section_dates": [
    {"structure_id": "B", "required_handover_date": "2026-09-26", "estimated_finish_date": "2026-09-27"}
  ]
}
```

前端标题分别为“按本计划需移交日期”“预计施工完成日期”，提示“以路床在所示需移交日期当天开工前完成移交为前提”。日期覆盖施工和正工期配套任务，不是实际移交确认或所有方案中的最迟移交承诺。

## 异常与兼容

下述MODEL_INVALID指求解器/场景求解结果；直接`/api/solve`沿用现有HTTP 422输入校验响应，以相同诊断代码报告输入错误，不改变既有传输契约。

- 直接solve无scope：根据实际任务补齐规则范围，仍强制后置。
- scope遗漏pending、伪造段/层计数或新规则同时声明blocked：MODEL_INVALID、PAVEMENT_REFERENCE_INVALID；非法三态/日期沿用PAVEMENT_ROADBED_INVALID。
- 旧scope无新策略且仍含blocked段：MODEL_INVALID、PAVEMENT_INPUT_OUTDATED，提示重新生成。不能只删blocked而宣称恢复了未提交任务。
- pending缺数量/工效/资源：沿用对应诊断，不默默跳过。全pending合法时允许条件起排，不再因全部待定报“无可开工段”。无启用任务仍有空数据诊断。
- 与顺序或里程碑矛盾：可证明的输入问题提前报告，其余返回INFEASIBLE，不松绑或宽松重试；不按关系方向误判SS/FF/SF。
- UNKNOWN/INFEASIBLE/MODEL_INVALID无伪造日期，保留状态/原因/可用范围；不混入上一次成功日期。
- 历史结果没有新字段，继续按自身blocked范围展示，不能用当前主数据补日期。无pending的合法旧输入与桥梁行为保持。
- 沿用既有结果序列化/导出路径保留新字段，不新增格式，不写回真实主数据/配置。
