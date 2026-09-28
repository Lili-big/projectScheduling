# 研究结论

## D1 / D2：缺日期在当前实现中是全局阻断

证据：`04-demo/backend/app/project_master/validation.py`、`scheduling_adapter.py`以及`04-demo/backend/app/scheduling/solver/strategies/pavement.py`。需要共同修改三处，单改页面或在生成时跳过待定段仍会被materialize阶段拦截。

决策：状态为显式施工段参数；仅对合法handed_over/pending解除缺日期校验。无状态的旧日期仍生效，无状态无日期保守待定。拒绝把“已移交”写成当天日期，也不从任意备注推断业务许可。

## D3：只约束首道工序不够

已支持SS/FF/SF；只在首道任务加日期约束不能保证后续或前置配套不会提前。既有生成器在各核心任务上读取路床日期，但配套属性和低层求解仍需覆盖三态。

决策：全部核心及配套任务继承段级最早日期，直接求解也执行同一规则。目标函数与资源路径不变。

## D4：排除待定段必须显式显示范围

`GeneratedScheduleInput`已有source_summary，`ScheduleResult`已有stats，结果总工期原本只针对输入任务。直接少生成16项任务会隐藏缺口。

决策：新增小型类型化范围元数据，经ScheduleInput带到生成与结果；复用summary/stats承载，展示4段未排程。全待定沿用现有MODEL_INVALID加专门业务码与中文空态，避免为一个空态扩大全项目求解状态枚举。

## D5 / D6：沿用当前保存与导入

主数据参数、稳定ID、版本确认与并发保护已存在；新字段不需要SQLite新表。当前客户状态映射来自用户明确解释和25行源表。

决策：使用现有参数持久化及快照导入；一次升级当前版本，保留历史，不启动时全库扫描。没有需要外部资料或新依赖解决的未知问题。
