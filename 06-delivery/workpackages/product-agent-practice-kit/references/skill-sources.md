# Skill 来源与版本

本文件用于分发审计和后续升级比较。

## 分发说明

- 快照日期：2026-07-28
- 来源类型：通用 Codex Skill 与项目 Spec Kit Skill 模板。
- 中文化：工具包内触发描述、正文、界面提示、模板和脚本输出已经统一为中文；稳定 Skill 名称、命令和代码字段保留英文。
- 分发目的：作为团队启动工具包的项目本地执行副本；安装或升级时仍需审查目标项目规则。
- 敏感性检查：未包含客户原件、项目绝对路径、账号、密钥或个人配置。

## 来源记录

| Skill | 来源相对路径 | 显式版本 | 入口SHA-256 |
|---|---|---|---|
| `requirement-discovery` | `requirement-discovery/` | 中文分发版 `1.0.0` | `4df7e051a8548762f9207697a7f98bde30c416e6635c00072227b9afa0c98af3` |
| `write-prd` | `write-prd/` | 中文分发版 `1.0.0` | `46057e8be0a1a175b274def990c71fe2dc2647401faccb2c3cf5bc3fa0d9eaaf` |
| `manage-speckit-project-skills` | `manage-speckit-project-skills/` | 中文分发版 `1.0.0` | `a7b55412a1b07b297cf80efa9026c40d00aa27eced1e59b8bb8a21b5648408a8` |
| `project-skill-template` | 本工作包新建 | 中文分发版 `1.0.0` | `c37133363732ff106bbafbf5d27210f0435148a5c6c086522d3b17124ca17edb` |

入口SHA-256对应各Skill的 `SKILL.md`。`manage-speckit-project-skills/assets/manifest.json` 继续记录其内置Spec Kit模板版本。

## 校验快照

```powershell
Get-FileHash skills/requirement-discovery/SKILL.md -Algorithm SHA256
Get-FileHash skills/write-prd/SKILL.md -Algorithm SHA256
Get-FileHash skills/manage-speckit-project-skills/SKILL.md -Algorithm SHA256
```

## 升级规则

1. 先读取目标项目 `AGENTS.md` 和项目本地Skill。
2. 比较差异，识别通用改进和项目特例。
3. 不用本快照静默覆盖项目本地适配。
4. 发布新工具包时更新快照日期、中文化说明、入口哈希和受影响说明。
5. Spec Kit 模板升级使用 `manage-speckit-project-skills status` 先做只读检查。
