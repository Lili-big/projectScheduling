# 数据模型：下部结构尺寸摘要与截面保留

本功能新增前端派生的类型专用摘要键，并让现有客户数据构建保留 `dimensions_m` 通用参数；不新增数据库表、列或 API 顶层字段。

## 1. 米制尺寸表达式 `MetricDimensionExpression`

| 字段 | 类型 | 说明 |
|---|---|---|
| `sourceText` | `string` | 原始文本，例如 `16.5*16.5*6.0`、`3.0*4.0` |
| `signatureValue` | `string` | 去除无意义空白、规范化乘号后的稳定文本 |
| `displayText` | `string` | 规范化乘号并在末尾保留一次 `m` |
| `kind` | `rectangular \| variable_section \| multi_dimension` | 仅用于诊断和显示，不计算面积 |

### 规则

- 接受以正数为尺寸段、以 `*`、`x`、`X`、`×` 连接的表达式；可保留源数据中的 `/` 变截面语义。
- `*`、`x`、`X` 转为 `×`；空白不参与签名。
- 保留文本小数精度，例如 `2.0` 不规范化成 `2`。
- 单位仅在整个表达式末尾出现一次；已有明确 `m` 时不得重复追加。
- 无法识别的普通文字不成为尺寸表达式。

## 2. 墩身截面标识 `PierSectionIdentity`

### 圆形截面

| 字段 | 来源 | 规则 |
|---|---|---|
| `kind` | 常量 | `circular` |
| `value` | `diameter_m` | 有限正数或有效数值文本 |
| `unit` | 参数单位或代码推导 | 默认 `m` |
| `displayText` | 派生 | `φ{value}{unit}` |

### 矩形或变截面

| 字段 | 来源 | 规则 |
|---|---|---|
| `kind` | 尺寸表达式 | `rectangular` 或 `variable_section` |
| `value` | `dimensions_m` | `MetricDimensionExpression.signatureValue` |
| `unit` | 参数语义 | `m` |
| `displayText` | 派生 | 如 `2.0×1.5m` 或 `8.0×6.0/4.0m` |

### 冲突与缺失

- `diameter_m` 与 `dimensions_m` 同时有效：`conflict`，不得静默选择。
- 两者均无效：`missing`，显示“截面尺寸未提供”。

## 3. 类型专用结构摘要键

| 构件类型 | 签名参数 | 明确排除 |
|---|---|---|
| `pile` | 工艺身份、`diameter_m` 值/单位、构件单位 | `length_m`、`form`、其他参数 |
| `pier_body` 圆形 | 工艺身份、圆形截面标识、构件单位 | `height_m`、位置 `form` |
| `pier_body` 矩形/变截面 | 工艺身份、尺寸表达式、构件单位 | `height_m`、位置 `form` |
| `cap` | 既有完整参数、工艺身份、构件单位 | 无新增排除；只调整尺寸显示 |
| 其他三类 | feature 057 既有签名 | 本功能不变 |

同签名构件的 `quantity` 相加，输出继续使用 `WorkpointStructureSummaryItem`，不持久化。

## 4. 客户原始截面映射

原始“墩柱/直径（m）”单元格映射：

```text
single positive number
  → param.diameter_m = number

valid dimension expression
  → param.dimensions_m = original text

empty
  → neither parameter

invalid non-empty value
  → build/import diagnostic; do not silently drop
```

原始“位置”与“墩高（m）”继续分别映射为 `form`、`height_m`，但不进入墩身摘要键。

## 5. 项目主数据版本

```text
原始客户工作簿
  → build_lugu_project_master.mjs
  → 新统一主数据工作簿（diameter_m / dimensions_m）
  → 现有导入预检
  → 新 draft 版本
  → 确认后成为 current confirmed version
```

- 旧版本保留，不原地更新组件参数。
- 导入有阻断错误时不得确认新版本。
- 本地数据库是持久状态，不进入 Git；跟踪的统一工作簿和检查报告继续按客户验证资产管理。

## 6. 不变量

- 桩长和墩高仍保留给排程，不因摘要简化被删除。
- 数量、工艺、位置、资源池和求解输入不由摘要逻辑改写。
- 等价输入顺序变化不得改变摘要输出。
- 所有非空原始墩身截面必须进入直径、尺寸或明确诊断之一。
