# 数据模型：待移交附条件排程

## 不变的事实与持久化

保留现有三态、真实日期及备注字段：dated有合法日期，handed_over/pending不伪造日期。同段施工和配套任务状态/日期必须一致。工期、数量、层序、工效、资源、关系及主数据/配置持久化均保持，无迁移。

## 范围扩展

沿用`PavementHandoverScope`四个字段：total_section_count、included_section_count、included_layer_count、blocked_sections。新增：

| 字段 | 类型 | 含义 |
|---|---|---|
| pending_policy | 可选字面值`strict_last` | 新生成及新求解范围的规则标记 |
| pending_sections | 可选`PavementPendingSection[]` | 纳入的待移交段，无待定写空列表 |

`PavementPendingSection`包含structure_id、section_name、reason（均string）和component_ids（启用核心层ID列表）。配套任务不重复计层。正常段数由included_section_count减pending段数推导；当前预期25段100层，其中pending 4段16层。新规则blocked_sections为空，该字段保留历史排除语义。

新增字段在Python缺省None、None时省略序列化；TypeScript可选。历史负载和桥梁不被动增加字段。不复用“blocked”表示已经纳入的附条件任务。

## 成功日期扩展

`PavementSummary.pending_section_dates`为可选`PavementPendingSectionDates[]`，每个有任务的pending段恰好一项：

| 字段 | 类型 | 来源 |
|---|---|---|
| structure_id | string | 施工段ID |
| required_handover_date | ISO date | 该段全部实际任务最小start_date |
| estimated_finish_date | ISO date | 该段全部实际任务最大finish_date，含末日 |

段名和原因关联同一结果stats中的pending_sections，不从当前主数据取。仅新规则可行结果写入；无pending可写空列表，历史摘要缺省省略。失败不创建日期项。

## 校验与转变

1. 从任务属性解析N/P分组，包括施工和正工期配套任务；B=max正常end，无正常为0，全部pending start >= B。scope不能覆盖事实。
2. 输入有scope则核对计数、状态、重复/缺失段及核心层ID；停用不生成任务，空数据沿用既有诊断，不谎报完整可求解范围。
3. 直接输入无scope，从实际任务推导并强制strict_last；无法恢复未提交的施工段。旧输入含blocked且无新策略时要求重新生成。
4. UNKNOWN/INFEASIBLE/MODEL_INVALID仍带可识别的范围/原因，不把不合法客户端范围冒充已验证数据。
5. 排程不改变主数据。用户手动确认真实状态后才在下次生成时重新归组，旧输入/结果按既有机制失效；历史快照保留自身含义。
