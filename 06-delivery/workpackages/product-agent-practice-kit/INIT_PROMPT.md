# 初始化 Prompt

复制下面代码块中的全部内容，发送给当前项目中的 Codex：

```text
请使用当前项目中的“产品 Agent 项目启动工具包”完成初始化。

执行要求：

1. 在当前项目中查找 `toolkit-manifest.json`，其 `id` 必须为 `product-agent-starter-kit`。将该文件所在目录识别为工具包目录，将工具包目录的父目录识别为目标项目根目录。若找到多个工具包或父目录明显不是目标项目，停止并说明歧义。
2. 依次读取工具包中的 `toolkit-manifest.json`、`INITIALIZATION_CONTRACT.md`、`references/project-structure.md` 和 `references/skill-routing.md`。
3. 先读取目标项目已有的 `AGENTS.md`、项目说明、目录结构、现有 Skill、代码与测试入口，输出简短预检结论。
4. 按初始化协议执行“只新增、不覆盖”的安全初始化，并初始化项目本地 Skill。不得修改业务代码、删除或移动已有资产、安装全局 Skill。
5. 根据当前项目能够证明的事实填写 `.product-agent/project-profile.md`。无法确认的业务规则、产品范围和研发边界必须标记为“待确认”，不得推断补全。
6. 生成 `.product-agent/setup-report.md`，记录创建、复用、跳过、冲突、验证结果、待确认项和推荐的第一个任务。
7. 初始化完成后告诉我：
   - 当前状态是“可开始”“部分可用”还是“已阻塞”；
   - 我接下来只需要确认什么；
   - 第一条可以直接发送给你的产品任务是什么。

本消息只授权工具包定义的项目内、可逆、增量初始化操作。若已有项目规则与工具包冲突，以目标项目现有规则为准，并停止冲突部分。
```
