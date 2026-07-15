# 实施计划：三方案生成前 LLM 项目信息下载

**分支/目录**：`025-llm-project-context-export` | **日期**：2026-07-10 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/025-llm-project-context-export/spec.md` 的功能规格

**说明**：本模板由 `/speckit-plan` 填写。执行流程以 `.specify/templates/plan-template.md` 和 `.agents/skills/speckit-plan/SKILL.md` 为准。

## 概要

在 AI 多方案比选执行“生成三方案”后，提供本次实际用于三方案 LLM 生成的精简项目上下文 JSON 下载。后端把现有私有上下文构造函数提升为唯一公共构造入口，在初始化流程中只构建一次并同时用于 LLM 调用与响应字段；前端只序列化响应中的 `llm_generation_context`，不重新拼装。下载仅存在于 AI 多方案比选主视图，初始化失败或场景变化时失效。

## 技术上下文

<!--
  请用当前项目真实情况替换本节占位内容。未知项标为“需澄清”，不要凭空补规则。
-->

**语言/版本**：Python 3.12（Docker 运行口径）、TypeScript 5.7、React 19、Node.js 22（部署口径）

**主要依赖**：FastAPI、Pydantic、React、Vite、lucide-react；不新增依赖

**存储**：不适用；上下文随初始化响应返回，浏览器临时生成下载对象

**测试**：pytest 后端单元测试、TypeScript/Vite 生产构建、AI 多方案比选页面手工验证

**目标平台**：本地 FastAPI + Vite 开发环境，以及 Netlify 前端 + Docker FastAPI 后端部署形态

**项目类型**：前后端 Web 应用的向后兼容接口扩展与页面下载交互

**性能目标**：不新增网络请求；下载准备只对单次上下文执行一次 JSON 序列化，不影响三方案生成耗时口径

**约束**：发送对象与下载对象同源；不改变 LLM 提示词、输出结构、回退策略和三方案解析；不含密钥、Endpoint、模型配置；不涉及 CP-SAT；不持久化文件

**规模/范围**：一个初始化响应字段、一个上下文构造函数、一个 AI 多方案比选下载入口及对应后端测试和前端构建验证

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- [x] 用户已明确确认直接实现，并再次澄清只导出三方案生成 LLM 的精简项目上下文。
- [x] `spec.md` 已引用来源文档、Demo 事实和真实代码链路。
- [x] 不涉及排程、工期或 CP-SAT；资源信息仅作为既有 LLM 上下文透传；共享响应字段影响已明确。
- [x] 输入六分区、响应字段、页面入口、失败态、失效规则和验收标准均可测试。
- [x] 未把本地回退样例或 Demo 数据提升为新业务规则。
- [x] Spec Kit 产物使用中文简体，并保留必要代码标识符。

## 项目结构

### 本功能文档

```text
specs/025-llm-project-context-export/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
└── tasks.md             # Phase 2 输出（由 /speckit-tasks 创建）
```

### 源码结构（仓库根目录）

<!--
  用本功能真实涉及的目录替换下方示例；删除未使用路径，不保留“选项”标签。
-->

```text
backend/
├── app/
│   ├── models.py
│   └── services/
│       └── ai_resource_scheduling_assistant.py
└── tests/
    └── test_ai_resource_scheduling_assistant.py

frontend/
├── src/
│   ├── types/scheduler.ts
│   ├── features/resourceAssistant/ResourceAssistantPanel.tsx
│   └── styles.css
└── package.json
```

**结构决策**：复用现有 AI 资源助手服务、初始化响应模型和 `ResourceAssistantPanel`，不创建新服务层或下载模块。后端负责生成唯一真实上下文；前端负责临时序列化和下载生命周期。

## 复杂度跟踪

> 仅当 Constitution 检查存在必须解释的违反项时填写。

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
无 Constitution 违反项。
