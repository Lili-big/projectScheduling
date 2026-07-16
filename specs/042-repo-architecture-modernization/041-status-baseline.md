# 041 状态基线

本文件冻结 `042` 开始实施时 `specs/041-girder-scheduling-integration/tasks.md` 的真实状态。架构重构只迁移所有权和入口，不得自动改变这些任务的完成标记或把规格目标写成当前能力。

## 1. 汇总

| 状态 | 数量 |
| --- | ---: |
| 已完成 | 74 |
| 未完成 | 21 |
| 合计 | 95 |

## 2. 当前已落地的主要实现映射

| 能力 | 当前实现入口 | 状态边界 |
| --- | --- | --- |
| 架梁领域模型、指纹、诊断 | `backend/app/girder_planning/` | 已实现并有专项测试 |
| 项目数据版本、方案版本和联合快照 DTO | `backend/app/models.py` | 已实现；本重构后由 contracts 聚合兼容 |
| 架梁工作点与实绩导入 | `backend/app/girder_planning/import_service.py`、`progress_import_service.py` | 基础导入已实现；完整实绩闭环仍部分完成 |
| 架梁校验、物料、路线和计划 | `backend/app/girder_planning/` | 已实现的部分以现有测试为准 |
| 综合排程 API | `backend/app/main.py`、`backend/app/services/integrated_schedule.py` | 已实现预览和求解入口 |
| 计划管控存储和预测 | `backend/app/services/plan_control_repository.py`、`progress_forecast.py` | 基线/快照/预测/调整已有；统一发布闭环未完成 |
| 前端架梁专项 | `frontend/src/features/girderPlanning/` | 基础流程已实现；发布、实绩编辑和部分比较仍未完成 |
| 前端计划管控 | `frontend/src/features/planControl/` | 当前能力以页面和 Node 测试为准 |

## 3. 未完成任务冻结清单

- T051、T052、T053：专项确认、方案比较、发布门禁及其测试。
- T057、T060：前端比较展示和 US3 验证记录。
- T062、T064、T065、T072：架梁实绩、剩余任务联合滚动和 US4 验证。
- T073～T079：旧系统黄金夹具、影子验证和经授权后的旧入口归档。
- T083、T088：前端重复计算入口清理和 041 自身收敛审计。
- T090、T091、T092：由收敛审计追加的发布闭环、实绩闭环和影子验证工作。

精确任务描述仍以 `specs/041-girder-scheduling-integration/tasks.md` 为准。本清单不替代历史规格。

## 4. 重构保护规则

1. 迁移文件时同步保留旧 import/API/类型入口。
2. 042 的测试只验证 041 当前已实现行为，不为未完成任务伪造完成证据。
3. 042 完成后重新统计 041 的 `[X]`/`[ ]`，预期仍为 74/21；若 041 在并行开发中真实推进，必须把差异归因到对应提交或用户改动。
4. 042 的 README、agent 和架构文档对上述未完成能力使用“部分完成”或“规格目标”，不得表述为当前完整能力。
