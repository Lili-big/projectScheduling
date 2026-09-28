# 现有实现核对

| 核对项 | 证据和决策 |
| --- | --- |
| 后端是否具备三项能力 | generation/pavement.py及生成API均已有；当前API实测25段、100任务、75关系，复用即可 |
| 当前页面为什么不完整 | TaskViewWorkspace.tsx先显示独立前端计算表，第二张任务表依赖模拟页手动生成；Workspace.tsx不会进入任务页时请求 |
| 工效来源是否一致 | 当前前端只取首个同类工艺及默认方案，未完整处理method_id、component方案；后端实际按方法/默认工艺和override/component方案选择。以生成任务的process_id/productivity_rule_id及计算结果为准 |
| 未完成路床条件能否看任务 | 当前生成API在业务validation中返回缺项且仍返回100任务，求解另有硬门禁；预览不应调用solve |
| 未确认关系是否会误显示0 | 当前后端仍可返回有错误诊断的临时边，前端既有pavementDependencyRows保留null间歇；展示结合当前规则状态，未知显示N，不把临时边当已确认 |
| 个别层缺项怎么办 | 后端可能跳过该层；前端按主数据保留待完善行，关系投影校核完整启用层序，避免显示跳层捷径 |
| 异步更新与现有结果 | 既有手动生成/求解状态共享，自动预览应有独立状态；用请求序号及输入指纹隔离，避免覆盖历史求解 |
| 为什么只删养生输入不够 | generation/pavement.py仍为每段末层生成readiness_conditions并要求wait_basis，solver也强制校验；必须同步排除末尾条件，否则页面无处填写仍会报错 |
| 已有层间数据如何保留 | 显式分段/统一dependency_rules优先；无显式规则时读取旧layer_conditions.wait_days并在关系行展示，编辑后写关系规则；已存非末层验收日期仍作下道工序日期下界，不跟随删除养生表丢失 |
| 是否清理历史末层数据 | 不清理，不自动写配置；本轮生成不使用末层wait_days/accepted_available_date，旧直接求解输入明确要求重新生成，避免不同入口计算口径不同 |
| 完成日期边界 | 现有end_offset是半开区间末边界，finish_date=start+end-1；原ready_date=start+ready。本轮业务结束显示finish_date，不把ready_date误当施工完成而多出一天 |

无外部研究或新增依赖，无未决关键业务问题。采用已有API计算工期，自动预览不自动求解。具体设计D1—D12见plan；最新调整并入066，不新建重复规格。
