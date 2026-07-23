# 共享契约：任务视图权威显示映射

## 请求

```http
POST /api/project-master/versions/{version_id}/task-view-display-map
Content-Type: application/json
```

```json
{
  "workpoint_ids": ["WP-BR-GFWJ", "WP-BR-GYX"]
}
```

约束：

- `version_id` 必填且必须存在。
- `workpoint_ids` 最多 500 项；服务端去除空字符串、去重并稳定排序。
- 空集合合法，返回同版本空映射。
- 请求是只读操作，不创建或修改持久化数据。

## 成功响应

```http
200 OK
```

```json
{
  "project_data_version_id": "pmv-example",
  "workpoints": [
    {
      "workpoint_id": "WP-BR-GFWJ",
      "workpoint_name": "高峰五家特大桥",
      "sort_order": 10,
      "work_sections": [
        {
          "work_section_id": "SEC-001:left",
          "work_section_name": "左幅第一联",
          "side": "left",
          "sort_order": 1
        }
      ]
    }
  ]
}
```

响应不包含 `components`、`parameters`、`source`、里程、备注或完整结构物对象。

## 完整性与顺序

- `project_data_version_id` 必须等于路径 `version_id`。
- `workpoints` 的 ID 集合必须与规范化请求集合完全相等，按 `sort_order, workpoint_id` 排序。
- `work_sections` 仅来自含非空 `section_code` 的权威结构物。
- `work_section_id` 与任务生成保持同一规则：`section_code + ':' + normalized_side`。
- 同一 `work_section_id` 对应多个结构物时，只返回 `sort_order` 最小者的显示投影。

## 错误响应

错误体沿用项目主数据稳定结构：

```json
{
  "detail": {
    "code": "PROJECT_MASTER_NOT_FOUND",
    "message": "..."
  }
}
```

| HTTP | code | 条件 | 前端行为 |
|---|---|---|---|
| 404 | `PROJECT_MASTER_NOT_FOUND` | 版本不存在，或任一请求工点不属于该版本 | 整体 error，显示通用重试态 |
| 422 | FastAPI validation detail | 请求体无效或超过 500 项 | 整体 error，不提交部分映射 |
| 503 | `PROJECT_MASTER_STORAGE_ERROR` / `PROJECT_MASTER_SERVICE_ERROR` | 存储或服务失败 | 整体 error，允许重试 |

前端不得解析 `message` 决定业务分支，也不得在任何错误下回退显示原始 ID。

## 前端契约

- 每个请求身份最多调用该端点一次；retry 会创建新 generation 并再次调用。
- 响应进入 ready 前，前端必须再次校验版本和工点集合完全相等。
- ready 结果只缓存到相同 `project_data_version_id + 规范化 workpoint_ids` 身份。
- 旧身份响应晚到时丢弃，不改变当前 loading/ready/error 状态。
