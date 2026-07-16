# 系统上下文

## 项目定位

本项目是桥梁施工排程的模块化单体 Demo。它把项目结构、工艺工效、工艺逻辑、资源、里程碑和策略组合为 `ScenarioInput`，生成任务图和求解输入，再由 OR-Tools CP-SAT 输出排程、资源分配、里程碑评价、诊断和方案比较。

当前实现还包含架梁专项联算、计划基线/实绩/预测/调整、AI 参数建议和 AI 资源方案助手。它适合产品验证和研发交底，不是具备正式用户权限、审计、项目隔离和生产数据治理的成品系统。

## 角色

| 角色 | 主要任务 | 当前入口 |
| --- | --- | --- |
| 计划工程师 | 配置场景、生成任务、求解并比较方案 | React 工作台、排程 API |
| 专业工程师 | 维护结构、工艺、资源、里程碑和架梁配置 | 各配置页签、导入与专项 API |
| 项目管理者 | 查看基线、实绩、预测和调整建议 | 计划管控页签/API |
| 产品/研发/测试 | 评审规则、验证行为、定位改动和回归 | `AGENTS.md`、`agent.md`、测试和 Spec Kit |

## 主链路

```text
结构/工艺/逻辑/资源/里程碑
          |
          v
     ScenarioInput
          |
          v
GeneratedScheduleInput / ScheduleInput
          |
          v
 fixed resources | min resources | resource cost
          |
          v
ScheduleResult / ScenarioSolveResult
          |
          +--> 方案比较与诊断
          +--> 架梁专项联合快照（启用时）
          +--> 计划基线 -> 实绩 -> 预测 -> 调整 -> 采纳
```

对应 HTTP 主链：`GET /api/demo-scenario` → `POST /api/generate-schedule-input` → 三类求解之一 → `POST /api/compare-scenarios`。

## 系统边界

- 浏览器：React/Vite 前端，维护编辑态、调用 API、展示结果和失效旧快照。
- 后端：FastAPI 模块化单体，拥有业务校验、任务生成、求解、导入、版本和本地持久化。
- 本地数据：`.local-data/` 保存演示配置、项目结构参数和计划管控仓储；不作为多用户生产数据库。
- 文件输入：Excel/资料文件只在明确导入接口处理；根样例 Excel 是当前 Docker 和本地兼容输入。
- 外部 AI：默认本地确定性路径；配置 `AI_PARAMETER_ASSISTANT_*`、`AI_RESOURCE_ASSISTANT_*` 或兼容配置后可调用外部模型。密钥不进入仓库。
- Supabase：存在工艺关系访问代码/环境变量，但不应被入口文档描述为当前所有数据的必需生产存储。
- Netlify：当前 `netlify.toml` 只发布静态前端；`tools/demo-api-mirror/` 是未接入生产发布的参考镜像，不是 FastAPI/OR-Tools 正式后端。

## 兼容边界

042 重构保持 45 个 `/api` 路由、`app.main:app`、旧 Python 导入、前端旧类型/API 导出、配置路径、稳定 ID/指纹和启动命令。兼容入口的删除需要未来独立规格和破坏性变更确认。
