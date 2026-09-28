# 数据模型：机组适用工艺与共享实例

## 既有 ResourcePool

| 字段 | 规则 |
| --- | --- |
| id | 稳定机组组ID，重命名或勾选工艺不改变ID |
| label | 用户维护的非空名称 |
| type | 原三类专用类型继续有效；新增可用pavement_paving_crew，类型不再限制显式多工艺能力 |
| compatible_process_ids | 唯一可编辑能力来源；引用当前process_library真实ID，去重；有效组新保存不得为空 |
| quantity / max_quantity | 非负整数，单位套；页面编辑数量时同步；实际展开按既有作用域规则 |
| transfer_days | 自然日非负整数；有效实例必须确认，0套/停用可null |
| enabled / scope / authorized_workpoint_ids / overrides | 延用既有含义；共享能力不能扩大工点范围 |

一个池只按数量生成实例，无论勾选几种工艺。有效数量以作用域解析为准。名称不承担兼容推断。

## Resource（可选新增字段）

`compatible_process_ids: list[str] | None = None`，None在序列化时省略，桥梁默认契约不变。路面新生成实例保存明确非空列表；列表来自其实际来源池，不按类型过滤掉跨工艺项。pool_id、资源ID、范围、转场均沿用原定义。

- 字段缺失/null：只对旧专用资源按原类型兼容。
- 显式空列表：无可用工艺，启用实例视为非法；不得按类型重新授权。
- 新通用类型缺能力：非法。

## PavementTaskContext（可选新增字段）

`process_id: str | None = None`，非空字符串，来源为实际选中的ProcessTemplate.id。生成的施工任务必须填写；配套任务不消耗主机组。保留process_type用于验证结构层类别。

新能力资源匹配缺process_id的旧任务时报“请重新生成任务”。完全旧式的专用Resource仍按原资源类型处理。不从任务名称或productivity_rule_id拆分推导工艺。

## 持久化及失效

池字段复用现有本地v5项目配置，无新表、无自动跨项目迁移。老专用池空能力在加载/旧生成入口转换为本类型当前工艺ID；保存入口拒绝有效组主动清空。通用池不享受此回退。

关系与工效不变。机组适用工艺、数量、名称、范围、启用、转场变化进入现有场景指纹，使生成任务和结果失效。保存失败保留编辑。损坏配置保留文件且明确错误，不重置为空模板。

## 当前客户配置的定向变更

仅pavement-project：既有pavement-cement_stabilized_base-pool保持ID，label改为“碎石/水稳共享机组”，compatible_process_ids设为当前碎石、水稳工艺ID；quantity=1、transfer_days=1维持。其他池、工效、工序、主数据版本和其他项目保留。实施前再次读取并备份；使用API提交，写入前发现变化必须重读合并。
