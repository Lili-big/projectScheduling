# 研究结论

本轮只核对直接影响展示含义的未知项，不增加算法研究。

| 问题 | 证据与结论 | 决策及替代方案 |
| --- | --- | --- |
| 能否只改前端？ | 069真实HTTP结果包含generated.schedule_input与result；任务properties保留起终桩号，结果含机组、等待和转场。 | 使用同次结果快照，不增加后端字段。拒绝用当前scenario补历史结果，避免输入改变后错配。 |
| 能否复用桥梁横道？ | Workspace.tsx的PlanTimelineView为平铺列表，仅有名称和横道，依赖桥梁显示映射；不含两级父子、关系箭头或里程轴。 | 复用样式令牌、日期边界概念，在scheduleResults内实现路面组件。提取通用平台会扩大本轮范围。 |
| “最晚移交日”怎么算？ | strategies/pavement.py::result_from_candidate将required_handover_date设为该段最早start_date；test_pavement_solver.py验证pending严格后置。 | 文案用“本方案最晚需移交日”，须当天开工前移交。不能说已优化出全局最迟日期。 |
| 技术间歇是否等于两道作业空档？ | result_from_candidate从ready_offset及零天配套的附加等待生成wait_intervals；测试覆盖链内等待、末尾不计和不重复。 | 显示已返回区间及真实reason；其他空档不定性为养生或转场。 |
| 所有段能共用里程轴吗？ | 真实快照有K、AK等前缀及K678+011—DK0+558；施工长度独立存储。 | 按工点/桩号系列/幅别分轴；跨系列等无法定位数据保留序号并降级。不用桩号差重算工程量，不从名称猜地理连接。 |
| 机组顺序从哪里取？ | 结果任务含assigned_resource_id/start_offset/end_offset，实际非零转场含精确from/to任务ID；没有独立resource_sequences字段。 | 对同机组非重叠任务按时间排序；连续同位置合为到访，返回保留。拒绝按桩号排序代替施工顺序。 |
| 零天转场可从记录缺失推断吗？ | result_from_candidate仅输出非零转场；pavement_heuristic.py::transfer_days为同位置0、不同位置使用资源配置天数。 | 优先真实转场记录；同已知位置或快照资源明确0可显示0，其余缺失显示未知，不吞掉历史缺字段。 |
| 无改善如何继续提示？ | 流只有started/solution/complete/error，无定期心跳；controller已有elapsed，但没保留started预算，Workspace只接status/solved。 | 保留预算，前端本地“已等待”计时＋活动状态，终态停止。不能声称每次动画是服务器心跳，不能假装优化百分比。 |

核对依据：04-demo/backend/app/scheduling/generation/pavement.py、solver/strategies/pavement.py及pavement_heuristic.py；04-demo/frontend/src/contracts/pavement.ts及pavementStream.ts、app/workflows/solveWorkflow.ts、features/scheduleResults/；对应既有路面测试。

本地证据：.local-data/logs/20260927-193733-pavement-live/http-final.json。它是历史验证快照，不是新一次试算。没有未解决的实施阻塞项。
