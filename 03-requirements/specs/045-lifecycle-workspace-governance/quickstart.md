# 快速验证：根目录生命周期工作区治理

## 当前阶段

本功能已完成批准清单的物理迁移并进入最终收敛阶段。以下命令验证当前七阶段路径；所有清理仍默认 dry-run，本功能不执行删除。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.specify\scripts\powershell\check-prerequisites.ps1 -Json -PathsOnly
git status --short --branch
git diff --check
```

## 实施前验证

1. 冻结所有受跟踪、未跟踪和忽略资产及其 SHA-256/状态。
2. 确认当前端口和后台进程，日志迁移前不得终止无关进程。
3. 校验工作包、清理策略和迁移清单符合 contracts 中的 Schema。
4. 展示逐资产清单并取得物理迁移确认。

## 实施后核心场景

### 生命周期导航

- 从根目录在两次进入内定位调研、方案、需求、Demo、验证和交付工作包。
- 每个阶段 README 包含完整契约字段。

### 独立工作包

- 运行 JSON 任务展示工作包，使用批准样例生成 HTML。
- 运行排程结果查看器并核对固定结果摘要。
- 运行泸古验证构建/校验并把临时输出写入工作包本地产物目录。
- 打开 AI 案例工作包，确认来源、当前成果、历史版本及 `orphaned` 关系可见。

### 安全清理

```powershell
# 预期只列候选，不删除
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\00-governance\repository-tools\cleanup-workspace.ps1
```

检查输出包含路径、类别、大小、原因和建议动作；持久状态、用户输入和正式成果候选数必须为 0。治理校验与清理 dry-run 分别计时，并断言在当前冻结仓库规模下单次总耗时不超过 30 秒。

### Demo 与工程回归

目标命令以迁移后的根入口为准：

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run verify:architecture
npm.cmd run verify
```

另需验证 Docker 构建、Netlify 配置、FastAPI 单服务、Spec Kit prerequisites 和项目 Skill 发现。

## 2026-07-17 路径兼容专项结果

| 专项 | 命令或检查 | 结果 |
| --- | --- | --- |
| Spec Kit | `check-prerequisites.ps1 -Json -PathsOnly` | `FEATURE_DIR`、spec、plan、tasks 均解析到 `03-requirements/specs/045-lifecycle-workspace-governance` |
| 项目 Skill | 扫描 `.agents/skills/*/SKILL.md` 并检查阶段权威入口 | 发现 11 个项目 Skill；`04-demo/skills/demo-algorithm-explainer/SKILL.md` 存在 |
| 工作包 | 校验 `workpackages.json` 与 9 个 `workpackage.json` | 9/9 可定位，无缺失 |
| JSON 任务展示 | `node 04-demo/standalone/json-task-viewer/scripts/build-task-view-html.mjs` | 生成 1 个工作区、5 个结构物、55 个任务的离线 HTML |
| JSON 排程评审 | `node 05-validation/workpackages/json-schedule-review/scripts/build-engineering-result-snapshot.mjs` | 生成 OPTIMAL、175 天、57 个任务、56 条资源分配的报告和 HTML |
| 固定结果查看器 | 检查两个 `*-viewer.html` | 2/2 存在，无运行时依赖 |
| 治理测试 | `python -m pytest 00-governance/repository-tools/tests -q` | 37 passed |
| 后端路径/文档/Docker 契约 | 相关 5 个测试文件 | 15 passed |
| Netlify | `node --test 04-demo/frontend/tests/deploymentContract.test.mjs` | 2 passed |
| 治理/文档/依赖 | 三个验证器 | 全部通过；仅保留已登记 `outputs` 本地缓存警告 |

## 迁移后验

- 清单内源路径消失、目标存在、哈希和跟踪状态一致。
- 清单外资产路径、内容和 Git 状态不变。
- 当前入口旧路径引用为 0；历史原文由迁移记录解释。
- 公开 API、共享契约、固定样例、正式二进制哈希和 042/043 兼容状态无未批准变化。
