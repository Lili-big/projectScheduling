# 数据模型：路面每日实际进度

## 1. 当前主数据投影（只读，不增加主数据实体）

每个结构层：project_id、master_version_id、workpoint_id、structure_id、component_id、名称、排序、幅别、桩号、施工长度 construction_length_m、宽度 width_m、厚度 thickness_m。沿用当前已确认主数据，不使用求解 quantity；缺失参数返回 null。

前端 task_id=`pavement:{component_id}`，父行ID与 `pavementTaskGroups` 一致。没有结构层ID的辅助行不可填报。父行不汇总重复的结构层长度。当前工序只有启用项；历史工序只在有实绩时列出。

## 2. 项目进度修订（新增表 pavement_progress_revisions）

| 字段 | 类型/约束 | 含义 |
| --- | --- | --- |
| project_id | TEXT PRIMARY KEY | 与当前主数据项目一致 |
| revision | INTEGER NOT NULL，非负 | 台账修订，未写入时语义为0 |
| updated_at | UTC ISO时间文本 | 最近一次实际改动提交时间 |

GET不为读取创建记录。PUT在事务内按需创建修订行；有效改动批次成功后加1。空改动或值完全相同的批次不递增；仍需校验版本令牌。

## 3. 每日完成记录（新增表 pavement_daily_progress）

| 字段 | 类型/约束 | 含义 |
| --- | --- | --- |
| project_id | TEXT NOT NULL | 项目隔离 |
| component_id | TEXT NOT NULL | 稳定结构层身份 |
| progress_date | TEXT NOT NULL，YYYY-MM-DD | 施工日，不是录入时间，不带时区 |
| completed_length_m | TEXT NOT NULL | 规范十进制非负长度，最多3位有效小数 |
| source_version_id | TEXT NOT NULL | 该条最后保存时所用主数据版本 |
| updated_at | UTC ISO时间文本 | 最近更正时间 |

主键 `(project_id, component_id, progress_date)`；按该前缀读取项目全部记录。source_version_id与component_id关联历史components复合键，删除策略RESTRICT，不允许删除主数据版本时级联清空实绩。项目归属在同一写事务校验。版本号不进入主键，主数据发布新版本不会复制或清空日记录。

清空格删除对应记录；显式0保留。覆盖某天只更新该键。DB不保存累计、剩余、超量标志或第二份可编辑工程量。

## 4. 计算与数值

- 后端 Decimal 精确累计每日长度；前端每日编辑采用千分之一米的精确单位累计，在数值无法安全表达时提示非法输入，不截断。
- 已完量=本工序所有已保存日期合计，加上草稿相对已保存值的变化。
- 剩余量=当前施工长度−已完量；超量=max(已完量−当前施工长度,0)。未填长度时剩余及超量为null，已完可正常汇总。
- 原始主数据长度、宽厚不按输入精度回写。展示仅做稳定数字格式化。
- 列显示月份、折叠、菜单显隐均不影响累计；输入小数尾部0不构成额外精度，非零第4位小数拒绝。

## 5. 历史工序

当前禁用的同ID工序使用当前名称/维度；当前已移除的工序从最近一次记录的source_version_id取名称和尺寸并标明“历史主数据”。日记录全部保留，只读。重新启用同ID时回到当前表，使用当前维度；新建同名不同ID不继承历史实绩。

## 6. 事务与状态

读取在一个数据库快照中取得当前版本、修订和记录。写入用已有 `BEGIN IMMEDIATE`：查当前版本→比较expected令牌→验证全部cells及启用/项目归属→应用全部变动→递增revision→提交。任何错误回滚全部批次。主数据版本并发确认在同一SQLite写锁下串行，不能用事务外的旧校验结果写入。

前端状态：loading → ready（无记录也为ready）→ dirty → saving → ready；失败回dirty+error；409进入conflict并保留草稿。重新加载不会自动消除冲突：先展示已保存值与本地值供核对，用户选择后才允许基于新令牌再次保存。记录已在服务器保存但响应丢失时，重试的409也按此流程核对，不重复累加。

项目切换时隔离草稿与请求；没有已确认主数据或本地项目主数据待保存时禁止填报，不能把未保存的结构层写进台账。

## 7. schema2→3

只增加上述两表，不重写现有表和业务数据，保留既有索引及高版本拒绝行为。先在含已确认版本的临时v2库上验证升级、重复初始化、重新建立repository后读回。实际服务启用新版本前用SQLite一致性备份保存当前库；schema升级与备份不能在仅确认设计阶段执行。
