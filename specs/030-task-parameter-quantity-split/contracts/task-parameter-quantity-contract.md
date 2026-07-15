# 接口契约：任务结构物参数与工程量拆分

## 1. 适用接口

- `POST /api/import-bridge-params`
- `POST /api/import-local-bridge-params`
- `POST /api/apply-project-structure-params`
- `POST /api/generate-schedule-input`
- 复用相同场景与任务对象的求解、基准计划和进度反馈接口
- Netlify Demo 中相同路径的响应镜像

本功能只增加向后兼容字段并收敛新生成 `quantity_label` 的含义，不新增接口或状态码。

## 2. 结构构件增量字段

```json
{
  "id": "P01-CAP",
  "component_type": "cap",
  "structure_parameter_label": "6.25m × 1.5m × 1.8m",
  "quantity": 1,
  "quantity_label": "1个",
  "properties": {
    "dimensions_m": [6.25, 1.5, 1.8],
    "count": 1
  }
}
```

`structure_parameter_label` 为可空字段。旧请求未携带时必须正常校验和处理。

## 3. 墩柱构件示例

```json
{
  "id": "P01-BODY",
  "component_type": "pier_body",
  "structure_parameter_label": "双柱式，柱径1.8m，2根",
  "quantity": 10,
  "quantity_label": "10m",
  "properties": {
    "form": "双柱式",
    "diameter_m": 1.8,
    "count": 2,
    "height_m": 10
  }
}
```

当未来提供逐柱高度时，可以在 `properties.column_heights_m` 中携带列表；平均值写入任务工程量，但原始列表保留。

## 4. 任务响应增量字段

`POST /api/generate-schedule-input` 的 `schedule_input.tasks[]` 增加：

```json
{
  "id": "P01-BODY",
  "component_type": "pier_body",
  "structure_parameter_label": "双柱式，柱径1.8m，2根",
  "quantity": 10,
  "quantity_label": "10m",
  "duration_days": 21,
  "properties": {
    "form": "双柱式",
    "height_m": 10,
    "count": 2
  }
}
```

字段规则：

- `structure_parameter_label`：可空，禁止作为工期计算输入。
- `quantity`：当前工效使用的数值。
- `quantity_label`：纯工程量，禁止拼接结构尺寸与形式。
- `duration_days`：继续遵守现有向上取整和最少 1 天规则。

## 5. 上部任务示例

```json
{
  "component_type": "cast_in_place_continuous_beam",
  "structure_parameter_label": "连续刚构，9#墩~12#墩，86+160+86，标准段",
  "quantity": 8,
  "quantity_label": "8块"
}
```

```json
{
  "component_type": "cast_in_place_box_beam",
  "structure_parameter_label": "现浇箱梁，3#墩~6#墩，3×40",
  "quantity": 1,
  "quantity_label": "1联"
}
```

## 6. 历史兼容

以下旧对象仍然合法：

```json
{
  "component_type": "cap",
  "quantity": 1,
  "quantity_label": "6.25m × 1.5m × 1.8m，1个",
  "properties": {
    "dimensions_m": [6.25, 1.5, 1.8]
  }
}
```

读取规则：

1. 不要求历史对象补写 `structure_parameter_label`。
2. 展示层可从 `properties.dimensions_m` 派生结构参数。
3. 工期计算使用 `quantity` 和当前工效，不解析混合 `quantity_label`。
4. 保存或加载历史计划不得因为缺少新字段失败，也不得自动重写原文件。

## 7. 错误和诊断

- 缺少结构参数但工程量有效：任务正常生成，参数摘要为 `null`/页面 `-`。
- 墩柱没有有效平均高度：沿用任务生成验证消息，明确指出平均墩高无法计算，禁止生成错误工期。
- 工效工程量来源不受支持：沿用现有工程量/工效诊断，不静默回退到混合文本。
- 接口整体错误响应和状态码保持现状。
