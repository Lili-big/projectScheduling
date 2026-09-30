# 前后端接口：路面实际进度

沿用现有FastAPI与projectMasterApi错误处理，不修改已有调用。后端类型放 `04-demo/backend/app/contracts/project_master.py`，前端放 `04-demo/frontend/src/contracts/projectMaster.ts`。所有长度单位m。

## GET /api/projects/{project_id}/pavement-progress

读取当前主数据版本下的台账，不限定月份，保证前端全日期累计。无记录的有效项目返回200和空entries、revision=0；不是404。

响应 `PavementProgressView`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| project_id | string | 请求项目 |
| master_version_id | string | 本次读取的当前已确认版本 |
| revision | integer >=0 | 项目级台账修订 |
| rows | PavementProgressRow[] | 当前启用的工序主数据及统计 |
| historical_rows | PavementProgressRow[] | 停用/移除且有实绩的工序；只读 |
| entries | PavementDailyProgressEntry[] | 当前及历史工序的全部日记录 |

`PavementProgressRow`：component_id、workpoint_id、structure_id、section_name、component_name、side、section_code、start_chainage/end_chainage（string|null，原始桩号文本）、start_mileage_m/end_mileage_m（number|null）、source_version_id、status（active/disabled/removed）、design_length_m/width_m/thickness_m（number|null）、completed_length_m（number）、remaining_length_m/overrun_length_m（number|null）。名称/幅别使用既有主数据口径；排序与父子结构由任务投影复用，不依据返回数组另造任务规则。历史removed行尺寸来自source_version_id，界面明确标识历史。

`PavementDailyProgressEntry`：component_id（string）、progress_date（YYYY-MM-DD string）、completed_length_m（number，含0）；不返回null记录。缺失日键=未填，不能默认显示0。

## PUT /api/projects/{project_id}/pavement-progress

`SavePavementProgressRequest`：

```json
{
  "expected_master_version_id": "version-id",
  "expected_revision": 0,
  "cells": [
    {"component_id": "layer-id", "progress_date": "2026-09-01", "completed_length_m": 300},
    {"component_id": "layer-id", "progress_date": "2026-09-02", "completed_length_m": null}
  ]
}
```

- 两个expected字段必填。只提交改动格，不提交累计/剩余/尺寸；额外可写字段拒绝。
- 日期严格为合法YYYY-MM-DD，不接受时间戳或自动跨月纠正。
- 量为非负有限JSON number或null；拒绝布尔值、数值字符串、负数、非有限值、不安全数值及超过3位非零小数；null清除、0存储。累计超设计量不构成错误。
- 同请求重复component_id＋progress_date拒绝。必须是本项目当前已确认版本的启用路面结构层，不能写历史/其他项目/辅助行。
- 全部成功返回200及更新后的 `PavementProgressView`；不存在部分成功或按日追加累计。
- 本API不改变主数据版本、资源、场景配置及计划结果，不调用主数据确认后的排程失效钩子。

## 错误与页面状态

业务错误沿用 `detail.code` / `detail.message`；Pydantic格式错误保留现有422字段定位，前端兼容这两类错误格式。

| HTTP | code | 页面处理 |
| --- | --- | --- |
| 404 | PAVEMENT_PROGRESS_MASTER_NOT_FOUND | 提示先维护并确认项目主数据；禁止填报 |
| 409 | PAVEMENT_PROGRESS_MASTER_CHANGED | 当前版本已改变；保留草稿、重新读取并核对 |
| 409 | PAVEMENT_PROGRESS_REVISION_CONFLICT | 他处已修改；保留草稿、核对最新记录，禁止静默覆盖 |
| 422 | PAVEMENT_PROGRESS_INVALID_CELL | 格式、归属、启用状态、重复格或数值无效；标明对应格/原因，整批不写 |
| 422 | PAVEMENT_FEATURE_NOT_SUPPORTED | 非路面范围或参考镜像没有存储能力；明确不可用 |
| 503 | PAVEMENT_PROGRESS_STORAGE_ERROR | 存储不可用；保留草稿并允许重试，不显示保存成功 |

网络失败显示重试，不当成空项目或累计0。首次loading禁编；保存中禁编和重复提交；正常空白日格不报错。冲突重读后呈现改动格服务端值与本地值，需明确核对才能用新令牌保存。导航/月份切换保留草稿；关闭/刷新采用浏览器标准未保存提醒。

## 兼容与演示镜像

旧master和scheduler-config无需补进度字段；没有日记录保持空白。`04-demo/tools/demo-api-mirror/api.mts` 对两项路面进度路径返回现有422 `PAVEMENT_FEATURE_NOT_SUPPORTED`，不返回假记录或假保存成功。接口契约测试同时覆盖后端真实存储与镜像拒绝路径。新字段和路径纳入现有架构基线，旧接口保持不变。
