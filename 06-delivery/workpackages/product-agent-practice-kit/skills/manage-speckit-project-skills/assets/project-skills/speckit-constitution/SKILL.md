---
name: speckit-constitution
description: 根据用户提供或项目中可证明的原则创建、修订项目 Constitution，并同步检查依赖模板。适用于建立长期业务与工程不变量、修改治理原则或校验模板是否仍与原则一致。
---

# 项目 Constitution 管理

只操作 `.specify/memory/constitution.md`。该文件定义长期不变量，不承载单次需求结论。

## 工作流

1. 读取用户输入和现有 Constitution。文件缺失时，从 `.specify/templates/constitution-template.md` 初始化。
2. 识别所有 `[全大写占位符]`，结合以下来源填写：

   - 用户当前明确输入。
   - 项目 README、既有规则和历史 Constitution。
   - 无法确认的批准日期或原则使用 `TODO(字段): 原因`，不得猜测。

3. 按语义化版本决定版本号：

   - 主版本：删除原则或进行不兼容重定义。
   - 次版本：新增原则、章节或实质扩展约束。
   - 修订版本：澄清、措辞和非语义修正。

   版本类型存在歧义时，先说明判断理由。

4. 更新正文：

   - 原则名称简洁。
   - 规则使用可检查的“必须、不得、应当”。
   - 理由不明显时补充简短解释。
   - Governance 说明修订流程、版本策略和合规检查。
   - 除有理由保留的 `TODO` 外，不留未解释占位符。

5. 检查依赖：

   - `.specify/templates/plan-template.md`
   - `.specify/templates/spec-template.md`
   - `.specify/templates/tasks-template.md`
   - `.specify/templates/commands/*.md`
   - 项目 README、快速开始和 Agent 规则

   只有 Constitution 变化确实要求同步时才修改依赖文件。

6. 在 Constitution 顶部加入 HTML 注释形式的同步影响报告，包括：

   - 旧版本 → 新版本。
   - 修改、新增和删除的原则。
   - 已更新与待更新的模板。
   - 暂缓处理的 TODO。

7. 验证：

   - 版本与影响报告一致。
   - 日期使用 `YYYY-MM-DD`。
   - 不存在未解释占位符。
   - 原则可执行、可检查，没有无依据的模糊表述。

8. 写回 `.specify/memory/constitution.md`。

## 完成

报告新版本、升级理由、同步修改和仍需人工处理的事项，并提供一条建议提交信息。局部原则修改也必须完成版本判断和一致性检查。
