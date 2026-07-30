# Skill 目录

本目录用于初始化和维护项目执行能力，不要求产品经理记忆 Skill 名称。

## 可直接复用

| Skill | 建议位置 | 负责什么 | 不负责什么 |
|---|---|---|---|
| `requirement-discovery` | 项目本地 | 需求还原、证据分层、需求分级、方案比较、MVP与反证 | 不写正式Spec、不修改代码 |
| `write-prd` | 项目本地 | 把当前有效口径写成研发和测试可执行的中文PRD或规则交底 | 不把Demo实现强加给研发 |
| `manage-speckit-project-skills` | 项目本地 | 初始化、比较、升级项目本地Spec Kit副本 | 不直接执行Feature工作流 |
| `project-skill-template` | 项目本地 | 创建和检查项目专有Skill，封装项目路径、规则与验证命令 | 不替代业务Skill本身 |

## 由管理Skill分发到项目本地

```text
speckit-checklist
speckit-constitution
speckit-specify
speckit-plan
speckit-tasks
speckit-implement
```

这些文件位于：

```text
skills/manage-speckit-project-skills/assets/project-skills/
```

初始化到项目后，实际执行应调用：

```text
<project>/.agents/skills/speckit-*/
```

## 项目本地Skill应该封装什么

- 权威代码、资料和数据路径。
- 项目术语、业务不变量和禁止推断项。
- 固定样例、测试命令和浏览器视口。
- Demo边界、正式能力声明和停止条件。
- 该项目特有的下一阶段路由。

不应把以下内容写进项目Skill：

- 单次需求的结论。
- 某一用户的个人偏好。
- 可以由通用Agent推理完成的常识。
- 密钥、客户原始资料或个人路径。

## 安装与升级

1. 启动工具包将所有执行副本安装到目标项目 `.agents/skills/`，不要求同事预装全局 Skill。
2. 项目本地 Skill 随目标项目规则管理。
3. 升级前先比较差异，不用工具包模板静默覆盖项目适配。
4. 每次发布记录快照日期、中文化说明和 SHA-256；本包记录见 [skill-sources.md](skill-sources.md)。
