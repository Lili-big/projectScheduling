# 产品 Agent 项目启动工具包

## 目的

这个工具包只有一个用途：

> 把一个新项目或已有产品 Demo，初始化为可以进行需求分析、方案设计、Demo 验证和 PRD 交接的产品 AI Coding 工作区。

## 只需要三步

1. 解压 ZIP，把整个 `product-agent-starter-kit` 文件夹放到目标项目根目录。
2. 用 Codex 打开目标项目。
3. 打开 [INIT_PROMPT.md](INIT_PROMPT.md)，复制其中的初始化 Prompt，发送给 Agent。

不需要手工安装 Skill，不需要先创建目录，也不需要复制其他说明文字。

## 初始化后会得到什么

```text
目标项目/
├─ AGENTS.md
├─ .product-agent/
│  ├─ project-profile.md
│  └─ setup-report.md
├─ .specify/memory/constitution.md
├─ .agents/skills/
│  ├─ requirement-discovery/
│  ├─ write-prd/
│  ├─ project-skill-template/
│  └─ speckit-*/
├─ 01-inputs/
├─ 02-product-baseline/
├─ 03-requirement-discovery/
├─ specs/
├─ 04-demo/
├─ 05-validation/
└─ 06-deliverables/
```

`setup-report.md` 会说明：

- 创建、复用和跳过了哪些资产。
- 哪些 Skill 已经可用。
- 哪些项目事实已识别。
- 哪些业务信息仍需确认。
- 第一个产品任务应该如何开始。

## 输入

初始化时只需要当前项目本身，以及项目中已经存在的文档、代码、测试或 Demo。没有证据的信息会保留为“待确认”，Agent 不会自行补全业务规则。

## 运行

日常使用者只粘贴 [INIT_PROMPT.md](INIT_PROMPT.md) 中的 Prompt。Agent 会按照 [INITIALIZATION_CONTRACT.md](INITIALIZATION_CONTRACT.md) 执行预检、初始化、适配和验证。

初始化只允许：

- 创建缺失目录和文件。
- 安装项目本地 Skill 副本。
- 根据已有证据填写项目概况。
- 生成初始化报告。

初始化不允许覆盖已有文件、删除内容、修改业务代码、移动客户资料或安装全局能力。

## 成果

完成标准不是“目录已经生成”，而是：

- 项目执行规则、阶段目录和 Skill 可以被 Agent 发现。
- 产品口径确认和实施授权两个门禁已经生效。
- 项目事实、未知项和正式研发边界已经登记。
- 产品经理可以直接发起第一个需求分析任务。

工具包内的详细方法位于 `references/`，由 Agent 按需读取，产品经理无需逐份学习。

## 初始化完成后

确认 `.product-agent/setup-report.md` 的状态为“可开始”后，即可把解压出来的 `product-agent-starter-kit` 文件夹移出业务项目。不要把 ZIP 或临时工具包目录提交到业务仓库。

## 跟踪与保留

- 目标项目生成的 `AGENTS.md`、项目概况、决策、规格和验证证据按目标项目规则管理。
- 解压的启动工具包仅用于初始化，可在完成后移出项目。
- 客户资料、密钥、日志和缓存不得进入工具包。
