# 数据模型

## 施工段路床条件

通过现有`ParameterValue`存储，不新增SQLite表。

| 参数 | 类型 | 语义 |
| --- | --- | --- |
| roadbed_handover_status | text：dated / handed_over / pending | 指定日期 / 已移交 / 移交待定 |
| roadbed_available_date | date，可空 | dated的最早可用自然日；复用原字段 |
| roadbed_handover_note | text，可空 | 移交待定原因或补充说明，原备注仍保留 |

组合校验：dated必须有合法日期；handed_over和pending的当前有效日期为空。接口切换状态时清空有效日期；历史日期仍在旧版本中。未知状态、非法日期和矛盾组合拒绝保存。pending说明可空，页面用“移交日期未定，暂不可开工”展示原因缺省值。

旧数据：无status、有合法date→dated；两者均缺→pending并显示“尚未明确移交条件”；无status且date非法→错误。兼容解析不扫描remark，前端不得把缺失状态默认成handed_over。

主数据投影时将这三个段级参数传至每个层的properties；组件属性不得覆盖段级路床状态。生成的配套任务也携带同一条件。直接求解对同段冲突条件返回引用/状态错误。

投影的`StructureModel.properties`同时保留段级条件，以便没有启用层的施工段仍能保留移交状态；字段为空时不序列化，桥梁及旧输入保持兼容。无段级投影的旧路面输入从组件属性读取，但必须保证同段条件一致。

## 状态变化

三态间均可由用户显式修改。pending→dated需日期；pending→handed_over不需日期；dated/handed_over→pending清空当前有效日期。每次成功保存创建主数据新版本，现有派生输入失效，旧结果保留。

“已移交”不等于路面任务完成，不能给层任务设置完成标记。计划开始日期变化只改变求解相对偏移，不回写实际移交日。

## PavementHandoverScope

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| total_section_count | 非负整数 | 本次请求范围内的段数 |
| included_section_count | 非负整数 | 路床条件允许参与的段数 |
| included_layer_count | 非负整数 | 纳入段的启用核心层数，不含配套步骤 |
| blocked_sections | PavementBlockedSection[] | 待定段，顺序按现有主数据排序 |

`PavementBlockedSection`：`structure_id`、`section_name`、`reason`、`component_ids`（该段启用核心层ID列表）。未知或重复ID为错误；段总数=纳入数+待定数（主数据身份正常时）。层数在任务生成前统计，不把因其他错误未生成的任务视作已完成。

传递：`ScheduleInput.pavement_handover_scope`为可选，默认None且桥梁输出省略；生成source_summary和结果stats均以`pavement_handover`键保存同形对象。旧历史结果没有该对象时只显示已有结果，不捏造历史排除范围。

## 当前数据升级

源：本任务用户25行表及三次明确确认。实施前核对当前版本和段身份。

- dated：其余18段，原日期不变。
- handed_over：第7段左K675+760-K679+200；第10段左K683+580-K686+800；第19段右K683+580-K686+800。
- pending：第5段左K671+440-K672+000；第11段右K666+910-K667+200；第15段右K671+551-K672+200；第25段平果互通连接线LK0+000-LK0+454.768。

所有稳定ID、段顺序、桩号、长度、9.2m宽度、层启用和厚度密度不变。按历史快照保留原备注与来源；不从层的启用字段推导路床状态。18+3=21段、84个核心层可纳入；4段16层待定。其他资源、工效、养生和转场仍按原校验。
