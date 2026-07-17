# 实施计划：AI资源助手分步求解与独立推荐

**分支/目录**：`023-stepwise-resource-solve` | **日期**：2026-07-10 | **规格**：[spec.md](spec.md)

## 概要

将 AI 资源助手原先“一次请求串行求解三方案并同步生成 LLM 推荐”的流程拆成用户驱动的四个按钮。每个方案独立求解、立即展示并刷新部分指标；三套结果齐全后，用户再独立触发确定性推荐和 LLM 解释。本次只改变接口编排和页面状态，保留现有 CP-SAT 和三方案生成逻辑。

## 技术上下文

**语言/版本**：Python 3.12、TypeScript、Node.js 22。

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6。

**存储**：不适用；Demo 页面内存保存当前方案与本轮结果。

**测试**：pytest、前端 TypeScript 构建、现有默认场景手动接口验证。

**目标平台**：本地 FastAPI 服务与 Vite/静态前端；Netlify 仅提供静态前端。

**项目类型**：前后端 Web Demo。

**性能目标**：一次方案点击仅等待对应 CP-SAT 结果；推荐请求不参与任一求解请求；刷新对比不触发 CP-SAT 或 LLM。

**约束**：保持现有求解预算、通用 90 秒请求超时、资源方案生成、CP-SAT 输入和算法规则不变；不新增持久化或异步任务系统。

**规模/范围**：资源助手页面、共享类型、API 客户端、FastAPI 路由、资源助手服务和对应后端测试。

## Constitution 检查

- 已完成需求澄清；用户确认采用“完整三方案后才允许推荐”。
- `spec.md` 已引用现有验证说明、规格、页面与服务事实。
- 排程规则不变；已明确输入、输出、状态、失效和 LLM 失败回退。
- 前后端契约会新增独立单方案、结果对比和推荐请求，旧批量接口保留兼容。
- 所有 Spec Kit 产物使用中文简体。

**设计后复核**：通过。不存在新增算法规则、未确认业务口径或 Demo 临时规则上升为产品规则的情形。

## 项目结构

```text
backend/
├── app/models.py
├── app/main.py
├── app/services/ai_resource_scheduling_assistant.py
└── tests/test_ai_resource_scheduling_assistant.py

frontend/src/
├── api/schedulerApi.ts
├── domain/resourceAssistant.ts
├── features/resourceAssistant/ResourceAssistantPanel.tsx
├── features/resourceAssistant/MetricComparisonTable.tsx
└── types/scheduler.ts

specs/023-stepwise-resource-solve/
├── research.md
├── data-model.md
├── contracts/resource-assistant-stepwise-api.md
└── quickstart.md
```

**结构决策**：复用现有资源助手服务、领域状态辅助函数和展示组件；不新增独立模块或依赖。
