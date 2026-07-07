# 数据模型：第二阶段可见墩距路径剪枝

## 路径候选节点

| 字段 | 含义 |
| --- | --- |
| `representative_task` | 代表当前路径节点的任务 |
| `bridge_id` | 桥梁标识 |
| `component_type` | 构件类型 |
| `process_name` | 工序 |
| `side` | 幅别，通常为 `L` 或 `R` |
| `support_index` | 墩号数字 |

## 可见墩距索引

| 索引 | 计算方式 | 用途 |
| --- | --- | --- |
| 同幅可见序列 | 按桥梁、构件类型、工序、幅别聚合候选墩号并排序 | 判断同幅连接是否在窗口 2 内 |
| 跨幅可见序列 | 按桥梁、构件类型、工序聚合左右幅候选墩号并排序去重 | 判断跨幅连接是否在窗口 1 内 |

## 诊断字段

| 字段 | 含义 |
| --- | --- |
| `resource_path_sparse_support_window` | 兼容保留的同幅窗口，值为 2 |
| `resource_path_sparse_same_side_window` | 同幅可见墩距窗口，值为 2 |
| `resource_path_sparse_cross_side_window` | 跨幅可见墩距窗口，值为 1 |
| `resource_path_transition_arc_count` | 第二阶段实际建模的路径候选弧数量 |
