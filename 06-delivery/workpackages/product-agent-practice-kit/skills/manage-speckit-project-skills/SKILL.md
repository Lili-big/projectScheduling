---
name: manage-speckit-project-skills
description: 从工具包内置模板初始化、比较或升级项目 `.agents/skills` 下的 Spec Kit Skill 副本。适用于新项目安装 speckit-checklist、speckit-constitution、speckit-specify、speckit-plan、speckit-tasks、speckit-implement，或检查、处理项目副本与模板的差异；不用于执行具体 Feature。
---

# 管理项目 Spec Kit Skill

`assets/project-skills/` 是可分发模板，目标项目 `.agents/skills/` 中的副本才是功能执行时使用的版本。

## 使用原则

- 初始化或升级前先读取目标项目 `AGENTS.md` 和 Constitution。
- 目标项目规则、脚本和验收门禁始终优先。
- 不用模板静默覆盖项目适配。
- 实际规格、规划、任务和实施必须调用目标项目的本地 Skill。

需要升级时先阅读 [升级策略](references/upgrade-policy.md)。

## 命令

只读查看状态：

```powershell
python scripts/manage_speckit_project_skills.py status --project-root <项目根目录>
```

预览初始化：

```powershell
python scripts/manage_speckit_project_skills.py initialize --project-root <项目根目录>
```

创建缺失副本：

```powershell
python scripts/manage_speckit_project_skills.py initialize --project-root <项目根目录> --write
```

预览升级：

```powershell
python scripts/manage_speckit_project_skills.py upgrade --project-root <项目根目录>
```

确认差异后升级：

```powershell
python scripts/manage_speckit_project_skills.py upgrade --project-root <项目根目录> --write
```

可重复使用 `--skill <名称>` 限定目标；`status` 可加 `--fail-on-drift` 将缺失或差异作为非零退出。

## 工作流

1. 确认目标是项目根目录，并存在 `.specify/`。
2. 先执行 `status`，区分缺失、一致和存在差异。
3. 初始化只补充缺失副本。
4. 升级前阅读差异，判断哪些属于项目适配。
5. 获得明确确认后再使用 `upgrade --write`。
6. 升级已有副本时，脚本会将旧版本备份到 `.codex-tmp/speckit-skill-backups/`。
7. 验证目标 Skill 格式，并报告创建、跳过、升级和备份结果。

## 停止条件

- 目标不是有效 Spec Kit 项目。
- 升级会覆盖尚未理解的项目差异。
- 用户只要求查看状态。
- 项目规则禁止写入。

不得因为模板较新就自动升级项目副本。
