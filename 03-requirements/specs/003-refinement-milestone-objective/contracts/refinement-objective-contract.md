# 契约：精排里程碑与工期目标函数调整

## 适用范围

本契约说明现有精排请求和结果字段在本功能后的业务含义。它不新增 API、字段或数据结构。

## 输入契约

| 输入 | 规则 |
| --- | --- |
| 里程碑列表 | `mode="hard"` 的已匹配里程碑在精排中必须满足；`mode="soft"` 的里程碑按软控制节点或普通软里程碑解释 |
| 目标项配置 | 保留 `control_node_late` 与 `makespan_and_soft_milestone` 内部 ID |
| 固定资源快排结果 | 仍可作为精排 warm start 和回退参考，不改变当前资源是否满足硬里程碑的判断流程 |

## 输出契约

| 字段 | 新口径 |
| --- | --- |
| `milestone_results` | 硬里程碑在精排成功结果中不得迟延；普通软里程碑可展示迟延和诊断罚分 |
| `objective_breakdown.control_lateness_days` | 只表示软控制节点迟延天数 |
| `objective_breakdown.soft_control_lateness_penalty` | 表示软控制节点迟延诊断值 |
| `objective_breakdown.soft_milestone_penalty` | 表示普通软里程碑诊断罚分，不参与精排目标贡献 |
| `objective_breakdown.weighted_objective` | 使用新目标口径的解释性加权汇总，总工期项只包含完工跨度 |
| `objective_terms_used.makespan_and_soft_milestone` | ID 保留，页面和文档展示为“总工期” |
| `objective_weights.makespan_and_soft_milestone` | 继续表示总工期目标权重 |

## 前端展示契约

| 页面位置 | 新口径 |
| --- | --- |
| 目标函数配置 | `control_node_late` 展示为“软控制节点迟延” |
| 目标函数配置 | `makespan_and_soft_milestone` 展示为“总工期” |
| 里程碑结果 | 软节点迟延继续展示，但不说明其进入总工期目标 |
| 精排诊断 | 硬里程碑不可满足时使用既有失败/回退诊断，不展示硬节点迟延的精排主方案 |

## 兼容性

- 既有目标项 ID、权重字段和结果字段保持可读。
- 已保存配置无需迁移。
- 文案和公式口径改变后，测试应确认旧目标名称不再作为当前目标项展示。
