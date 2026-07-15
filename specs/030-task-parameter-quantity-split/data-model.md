# 数据模型：任务结构物参数与工程量拆分

## 1. 设计原则

- 结构物参数和工程量是两个独立概念。
- 结构化尺寸与形式是权威数据；摘要文本仅用于展示。
- 工程量数值必须与当前工效 `quantity_source` 和工期表达式一致。
- 新字段全部默认可空，历史数据不迁移、不重写。

## 2. `ComponentModel`

| 字段 | 类型 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 必填 | 构件唯一标识 |
| `component_type` | enum | 必填 | 构件类型 |
| `structure_parameter_label` | string / null | 新增、可空 | 结构形式与几何参数的可读摘要，不参与工期计算 |
| `quantity` | number | 保留 | 构件的基础工程量；墩柱新数据保存平均墩高 |
| `quantity_label` | string | 保留 | 新数据只保存纯工程量文本 |
| `properties` | object | 保留 | 权威尺寸、形式、柱径、柱数、高度、来源追踪和历史兼容属性 |

### 校验规则

- `structure_parameter_label` 缺失不阻止历史数据加载。
- `quantity >= 0` 保持现有校验。
- 墩柱优先从 `properties.column_heights_m` 的有效值求平均；不存在时使用 `properties.height_m`/`heightM`。
- 结构参数摘要不得作为 `quantity` 的计算输入。

## 3. `UpperStructureComponent`

| 字段 | 类型 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `structure_type` | string | 必填 | 现浇箱梁、现浇连续梁或连续刚构等结构形式 |
| `support_range` | string | 必填 | 支座范围 |
| `span_group_expression` | string | 必填 | 跨径组合 |
| `structure_parameter_label` | string / null | 新增、可空 | 由结构形式、支座范围和跨径组合形成的稳定摘要 |
| `properties` | object | 保留 | 上部结构附加属性 |

### 校验规则

- 摘要字段缺失时可由三个现有结构字段生成。
- 同一连续梁组内各任务共享组级结构参数，并按任务补充节段类型。

## 4. `Task`

| 字段 | 类型 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `structure_parameter_label` | string / null | 新增、可空 | 任务来源结构物的参数摘要 |
| `quantity` | number | 保留 | 当前工效参与工期计算的工程量数值 |
| `quantity_label` | string | 保留 | 纯工程量文本，单位与 `quantity_source` 一致 |
| `duration_days` | integer | 保留 | 使用 `quantity` 和当前工效计算的工期 |
| `properties` | object | 保留 | 结构化来源及上部任务上下文，用于兼容派生 |

### 不变量

1. `structure_parameter_label` 不参与 `duration_days` 计算。
2. `quantity_label` 中不得混入尺寸、结构形式或柱数等参数说明。
3. `duration_days` 必须能由 `quantity`、当前工效和现有取整规则复核。
4. 工效切换可改变 `quantity`、`quantity_label`、`duration_days` 和资源候选，但不得改变 `structure_parameter_label`。

## 5. 十类任务映射

| 任务类型 | 参数摘要来源 | 工程量来源与单位 |
| --- | --- | --- |
| `pile` | 桩型、`diameter_m` | `pile_length_m` 时为 `m`；`count` 时为 `1根` |
| `cap` | `dimensions_m` | 构件数量，`个` |
| `spread_foundation` | `dimensions_m` | 构件数量，`个` |
| `ground_tie_beam` | `dimensions_m` | 构件数量，`个` |
| `middle_tie_beam` | `dimensions_m` | 构件数量，`个` |
| `pier_body` | `form`、柱径/截面、`count` | 平均墩高，`m` |
| `cap_beam` | `dimensions_m` | 构件数量，`个` |
| `abutment_body` | `form` 与已有尺寸 | 当前工效数量或高度 |
| `cast_in_place_box_beam` | 结构形式、支座范围、跨径组合 | 联数，`联` |
| `cast_in_place_continuous_beam` | 结构形式、支座范围、跨径组合、节段类型 | 块数或段数 |

## 6. 平均墩高

### 输入优先级

1. `properties.column_heights_m`：过滤不可解析值和小于等于 0 的值后取算术平均。
2. `properties.height_m` 或兼容键 `heightM`：当前统一单柱高度，直接作为平均墩高。
3. 仅当数据来源能证明 `ComponentModel.quantity` 是单柱/平均高度时使用 `quantity`。
4. 无有效值时形成工程量错误诊断，不生成错误工期。

### 示例

```text
结构形式：双柱式
柱数：2
每根高度：10m
平均墩高：(10 + 10) / 2 = 10m
标准节：4.5m/节
节数：ceil(10 / 4.5) = 3
工期：3 × 7天/节 = 21天
```

## 7. 兼容与状态变化

### 历史读取

- 缺少 `structure_parameter_label`：从 `properties` 或上部结构现有字段派生。
- 无法派生：展示 `-`，不修改历史文件。
- 旧 `quantity_label` 可能仍是混合文本，但不得被用于新工期计算或自动回写。

### 任务生成状态

```text
结构数据/工效配置
  → 生成稳定结构参数摘要
  → 按 quantity_source 生成工程量
  → 计算工期与资源候选
  → 返回任务视图
```

### 工效切换状态

```text
保留 structure_parameter_label
  → 重算 quantity 和 quantity_label
  → 重算 duration_days 和资源候选
  → 旧求解结果、方案对比和推荐失效
```
