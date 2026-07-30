# 可复制的产品 Agent 项目结构

本文件由初始化 Agent 按需读取，普通使用者无需手工照着创建目录。

## 推荐骨架

```text
project/
├─ AGENTS.md
├─ README.md
├─ .product-agent/
│  ├─ project-profile.md
│  └─ setup-report.md
├─ .specify/
│  ├─ memory/constitution.md
│  └─ templates/
├─ .agents/
│  └─ skills/
├─ 01-inputs/
│  ├─ raw/
│  └─ source-index.md
├─ 02-product-baseline/
│  └─ product-baseline.md
├─ 03-requirement-discovery/
│  ├─ decision-log.md
│  └─ <topic>/discovery.md
├─ specs/
│  └─ <feature-id>-<feature-name>/
├─ 04-demo/
├─ 05-validation/
│  └─ validation-ledger.md
└─ 06-deliverables/
```

## 目录职责与进入条件

| 位置 | 单一职责 | 进入条件 | 退出条件 |
|---|---|---|---|
| `.product-agent` | 保存初始化概况和结果 | 工具包开始初始化 | 项目状态、未知项和下一步清晰 |
| `01-inputs` | 保留原始输入及来源证据 | 收到资料 | 来源、版本、限制可追溯 |
| `02-product-baseline` | 还原当前产品事实 | 输入资料可读 | 事实、冲突、未知项分开 |
| `03-requirement-discovery` | 收敛问题、方案、MVP和决策 | 基线足够支撑分析 | 高影响业务语义已确认 |
| `specs` | 固化可实施、可验收的规格 | 产品口径已确认 | spec、plan、tasks一致且获实施授权 |
| `04-demo` | 验证产品行为 | 实施门禁已确认 | 核心场景可运行，Demo边界已声明 |
| `05-validation` | 保存机器和人工验证证据 | 有可验证实现或资料 | 验证范围、结果、风险可解释 |
| `06-deliverables` | 输出当前有效需求基线 | Demo评审和口径收敛 | PRD脱离聊天仍可执行和验收 |

## 权威关系

```text
原始材料不能被分析稿覆盖
当前产品基线不能被候选方案覆盖
用户最新确认的产品决策可以显式替代旧决策
Spec 是实现行为基线，Tasks 是实施范围基线
Demo 是验证载体，不是正式研发架构
PRD 只保留当前有效口径并引用验证证据
```

## 新项目最小初始化

1. 创建上述目录，不预建无用途的业务子目录。
2. 复制模板并替换所有 `[占位符]`。
3. 在 `AGENTS.md` 中登记实际验证命令。
4. 初始化需求发现、PRD、项目 Skill 模板和 Spec Kit 的项目本地副本。
5. 建立第一个 `SRC-001` 来源记录。
6. 用一个小型真实需求跑通全链路，再扩展治理规则。

## 不要复制的内容

- 客户原件、人员信息、账号、密钥和未脱敏截图。
- 某个 Demo 的临时 API、数据库模型和部署拓扑。
- 项目专有算法样例或生产数据。
- 没有来源、维护人或验收方式的历史文件。
