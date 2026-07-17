# 仓库与资产治理

## 根目录白名单

根目录只保留七个生命周期阶段、平台发现入口、入口文档和安装/构建/部署配置。新增业务文档、脚本、交付物、样例、日志或预览不得直接落在根目录。

| 资产 | 标准位置 | Git 策略 |
| --- | --- | --- |
| 仓库架构、策略和治理工具 | `00-governance/` | 跟踪 |
| 客户调研与来源证据 | `01-discovery/` 工作包 | 按输入敏感性 tracked 或 local-only |
| 方案比较和决策 | `02-solution-analysis/` | 跟踪 |
| PRD、算法规则和 Spec Kit | `03-requirements/` | 跟踪 |
| 主 Demo、样例和独立展示 | `04-demo/` | 源码/批准样例跟踪，本地输入/输出按工作包策略 |
| 客户/工程验证 | `05-validation/` 工作包 | 输入、脚本、结果分开登记 |
| 正式交付、案例和演示 | `06-delivery/` | 正式成果跟踪并保留哈希 |
| 状态、日志、缓存、临时和可再生成物 | `.local-data/` | 仅 README 跟踪，其余忽略 |

## 日志规则

- 前台调试保留终端输出；后台 stdout/stderr 使用 `04-demo/runtime/start_logged_process.ps1`。
- 落盘日志唯一标准位置为 `.local-data/logs/<启动时间>/`。
- 不在根目录或任何生命周期业务目录生成运行日志。
- 历史日志只移动、不自动删除；清理前确认对应进程已经停止。

## 交付物和生成物

- 路径名不能单独决定是否可清理；先按 `cleanup-policy.json` 判断状态、用户输入、正式成果、日志、可再生成物、缓存或临时类别。
- 正式交付物进入 `06-delivery/`，迁移和替换前后核对 SHA-256。
- 构建器进入所属阶段工作包的 `scripts/`，本地构建结果写入 `.local-data/archive/rebuildable/`。
- 预览、截图、检查 NDJSON 进入本地归档；Office `~$` 锁进入 `.local-data/locks/`；工具缓存进入 `.local-data/cache/`。

## 文档和路径变更

- 当前文档移动时同步更新 `README.md`、`AGENTS.md`、`agent.md`、阶段 README 和工作包引用。
- 规格权威路径为 `03-requirements/specs/`；通过 [`path-migration.md`](../history/path-migration.md) 解释历史旧路径。
- 架构、命令、API、配置或部署边界变化后运行 `npm.cmd run verify:architecture`。

## 新资产放置检查

1. 判断是否必须版本控制、是否可再生成、是否可能含凭据。
2. 声明阶段、工作包、资产类型、跟踪策略、保留类别和唯一主归属；无法归类时先补工作包/治理契约。
3. 正式二进制记录哈希；本地产物验证忽略规则。
4. 更新索引和引用，运行治理测试及 `git diff --check`。
5. 批量移动、取消跟踪或处理用户本地文件时，先提交逐文件清单并取得明确确认。
