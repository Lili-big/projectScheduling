# 数据模型：任务视图权威主数据快速加载

本功能只新增共享请求/响应和前端派生状态，不新增持久化表或字段。

## 1. 任务视图主数据请求身份

| 字段 | 类型 | 规则 |
|---|---|---|
| `project_data_version_id` | string | 必填、非空；来自当前规范任务 |
| `workpoint_ids` | string[] | 去空、去重、稳定排序后 0～500 项 |
| `request_key` | string | 由版本 ID 与规范化工点集合确定；仅前端状态使用 |

等价集合必须产生同一 `request_key`。版本或集合任一变化都产生新身份。

## 2. 批量显示映射请求

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_ids` | string[] | 0～500 项；服务端再次去空、去重、稳定排序 |

空集合直接返回同版本的空映射，不查询工点/结构物明细。

## 3. 最小工点显示投影

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_id` | string | 稳定工点/桥梁身份，必须属于请求版本 |
| `workpoint_name` | string | 权威工点/桥梁名称，不由 ID 推导 |
| `sort_order` | integer | 既有主数据顺序 |
| `work_sections` | WorkSectionDisplayProjection[] | 该工点下可用于任务视图的工区/幅别投影 |

## 4. 工区/幅别显示投影

| 字段 | 类型 | 规则 |
|---|---|---|
| `work_section_id` | string | 与任务生成一致，由权威 `section_code` 和规范 side 形成 |
| `work_section_name` | string/null | 权威工区名称；缺失时前端显示既有“名称不可用” |
| `side` | `left/right/shared/none` | 权威幅别；前端复用既有共享标签 |
| `sort_order` | integer | 同一 `work_section_id` 多结构时选择最小顺序 |

响应不得包含构件、参数、来源证据、里程或任务视图未消费的结构物字段。

## 5. 批量显示映射响应

| 字段 | 类型 | 规则 |
|---|---|---|
| `project_data_version_id` | string | 必须与路径版本一致 |
| `workpoints` | WorkpointDisplayProjection[] | 与规范化请求集合一一对应，按 `sort_order, workpoint_id` 稳定排序 |

完整性不变量：响应工点 ID 集合必须与请求集合完全相等；缺失、重复或额外工点均不能进入 ready 状态。

## 6. 前端加载状态

```text
null -> loading -> ready
                -> error -> loading (retry)
```

- `loading`：只包含当前身份和 generation，不包含可渲染映射。
- `ready`：只包含已通过完整性校验的完整响应。
- `error`：包含当前身份、generation 和通用错误消息，不缓存为成功结果。
- 身份切换会启动新 generation；旧 generation 返回不得改变当前状态。
