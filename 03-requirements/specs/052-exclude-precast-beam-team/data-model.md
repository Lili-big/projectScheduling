# 数据模型：工点资源排除预制梁班组

本功能不新增实体、字段、接口或持久化结构。

## 工点资源排除类型

沿用 050 的只读集合：

```text
excludedResourceCatalogTypes
```

新增成员：`precast_beam_team`。

### 规则

- 被排除类型不得进入 `resourceCatalogProjection` 输出。
- 被排除类型不得进入 `workpointResourceTypeProjection` 输出。
- 排除只影响工点资源目录和结构建议，不删除历史数据。
- 预制梁工艺中的 `resource_type`、`defaultResourceTypeByComponent` 和中文兼容名称保留，避免修改其他模块的兼容读取。
- `beam_erection_team` 不属于本次排除范围。
