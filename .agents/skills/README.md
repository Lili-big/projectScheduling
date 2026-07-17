# 项目 Skill 发现目录

`.agents/skills/` 是 Codex 固定项目级发现入口，不是业务资产的默认主目录。Skill 的生命周期所有权由 `00-governance/asset-policy/skill-catalog.json` 登记。

## 阶段所有权

- `speckit-*`：归属 `03-requirements`，负责规格、计划、任务、分析、实施和收敛；固定发现文件继续保留在本目录。
- `demo-algorithm-explainer`：业务权威材料归属 `04-demo/skills/demo-algorithm-explainer/`，本目录保留可发现入口。

## 维护规则

1. 新增或修改 Skill 前先声明阶段、服务的工作包、输入/输出、跟踪和保留策略。
2. Skill 内固定路径必须指向七阶段目标路径，不再把 `docs/`、`specs/`、`backend/` 或 `frontend/` 当默认业务根。
3. 发现入口和权威内容分离时，入口必须明确指向权威路径；不得维护两份会独立漂移的正文。
4. 更新 Skill 后同步更新 `skill-catalog.json`，运行相关专项和项目 Skill 发现检查。
5. 不引用未安装 Skill；缺少约定能力时说明缺口并选择已安装的最接近流程。

## Spec Kit 默认路径

活动功能目录统一位于 `03-requirements/specs/<编号>-<功能名>/`。`.specify/` 继续作为平台脚本和模板发现入口。
