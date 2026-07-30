---
name: project-skill-template
description: 创建或完善项目本地 Codex Skill，将项目专有路径、业务不变量、证据来源、验证命令、边界和停止条件封装为可复用能力。适用于团队希望把重复项目指令沉淀到 `.agents/skills`，或需要把通用 Skill 有意识地适配到具体项目。
---

# 创建项目本地 Skill

把重复的项目执行方法放进聚焦的本地 Skill，不持续扩张 `AGENTS.md`，也不让产品经理反复粘贴长 Prompt。

## 工作流

1. 读取目标项目 `AGENTS.md`、Constitution、相关权威文件和现有本地 Skill。
2. 确认这是会重复发生的项目专有任务，并列出至少两个真实触发示例。
3. 分开通用方法与项目规则：

   - 通用方法留在全局或共享 Skill。
   - 路径、领域不变量、固定样例、验证命令和本地边界进入项目 Skill。

4. 将 `assets/SKILL.template.md` 复制到 `.agents/skills/<skill-name>/SKILL.md`。
5. 替换全部占位符，删除不适用章节。
6. 保持正文精简；只有需要条件加载的详细规则才放到一层 `references/`。
7. 从 `assets/agents.openai.template.yaml` 创建 `agents/openai.yaml` 并替换占位符。
8. 使用 Skill Creator 校验器验证。
9. 对复杂 Skill 运行一次安全的真实任务前向测试。
10. 报告触发条件、产物、验证、项目依赖和升级责任人。

定稿或适配通用 Skill 前，读取 [项目 Skill 适配检查表](references/project-adaptation-checklist.md)。

## 必备内容

项目 Skill 必须说明：

- 哪些请求会触发。
- 应先读取哪些项目事实。
- 资产冲突时以什么为权威。
- 核心流程和明确输出。
- 不得跨越的产品或工程边界。
- 什么验证证明完成。
- 何时停止并请求确认。
- 产物交给哪个下一阶段或 Skill。

## 安全边界

- 不包含客户原件、密钥、个人绝对路径或单次任务结论。
- 不复制完整通用 Skill，只记录项目差异。
- 不静默覆盖已有项目 Skill。
- 不把“目录存在”写成“当前会话已经可用”。
- 不用 Skill 取代产品基线、正式规格或测试中的项目事实。
