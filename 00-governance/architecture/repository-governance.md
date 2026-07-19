# 仓库与资产治理

本文件只提供导航；可执行规则以机器策略和验证器为准，不在此复制第二套阶段、后缀或保留清单。

| 事项 | 权威来源 |
|---|---|
| 新资产分类、唯一主归属、跨阶段引用 | `asset-policy/placement-rules.json` |
| 根目录兼容入口 | `asset-policy/root-compatibility.json` |
| 生命周期阶段 | `asset-policy/lifecycle-stages.json` |
| 工作包登记与结构 | `asset-policy/workpackages.json`、工作包 Schema |
| 保留、清理保护和 dry-run | `asset-policy/cleanup-policy.json`、`repository-tools/cleanup-workspace.ps1` |
| 后台进程和日志 | `04-demo/runtime/README.md` |
| 仓库、文档和生命周期校验 | `repository-tools/validate_repository.py`、`validate_docs.py`、`validate_lifecycle_workspace.py` |

创建或移动资产时先用上述策略确定唯一合法路径；无法分类时停止。批量迁移、取消跟踪、删除或处理用户本地数据时，必须先核对逐项清单、回滚方式和所需确认。

治理变更后运行相关 pytest、验证器和 `git diff --check`；架构、命令、API、配置或部署边界变化再运行 `npm.cmd run verify:architecture`。
