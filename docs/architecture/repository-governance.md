# 仓库与资产治理

## 根目录白名单

根目录只保留入口文档、协作规则、安装/构建/部署配置和主模块目录。新增业务文档、脚本、交付物、样例、日志或预览不得直接落在根目录。

| 资产 | 标准位置 | Git 策略 |
| --- | --- | --- |
| 主应用源码与测试 | `backend/`、`frontend/` | 跟踪 |
| 当前产品文档 | `docs/product/` | 跟踪 |
| 算法与工程交底 | `docs/engineering/` | 跟踪 |
| 验证与调研 | `docs/validation/`、`docs/research/` | 跟踪 |
| 历史文档 | `docs/archive/` | 跟踪并标注状态 |
| Spec Kit 产物 | `specs/<编号>-<功能名>/` | 跟踪；不移动历史规格 |
| 可复现样例 | `examples/` | 跟踪且保持精简 |
| 可复用工具 | `tools/` | 跟踪，具有独立 README/验证入口 |
| 正式交付物 | `deliverables/` | 显式 allowlist 跟踪并保留哈希 |
| 预览、检查和可再生成输出 | `artifacts/` | 默认忽略 |
| 本地数据、运行状态和日志 | `.local-data/` | 忽略 |

## 日志规则

- 前台调试保留终端输出；后台 stdout/stderr 使用 `tools/local-runtime/start_logged_process.ps1`。
- 落盘日志唯一标准位置为 `.local-data/logs/<启动时间>/`。
- 不在根目录、`docs/`、`outputs/` 或 `deliverables/` 生成日志。
- 历史日志只移动、不自动删除；清理前确认对应进程已经停止。

## 交付物和生成物

- 文件位于 `outputs/` 不代表可以删除；先判断它是正式交付物、构建器还是可再生成中间件。
- 正式交付物进入 `deliverables/`，迁移和替换前后核对 SHA-256。
- 构建器进入 `tools/delivery-builders/`，通过参数把验证构建写到临时目录。
- 预览、截图、检查 NDJSON、Office `~$` 锁和本地运行时进入 `artifacts/` 或 `.local-data/`，不跟踪。

## 文档和路径变更

- 当前文档移动时同步更新 `README.md`、`agent.md`、`docs/README.md` 和架构文档引用。
- 历史 specs 不批量改写；通过 [`path-migration.md`](../archive/path-migration.md) 解释旧路径。
- 架构、命令、API、配置或部署边界变化后运行 `npm.cmd run verify:architecture`。

## 新资产放置检查

1. 判断是否必须版本控制、是否可再生成、是否可能含凭据。
2. 按上表选择唯一分区；无法归类时先更新治理规则，不临时创建根目录类别。
3. 正式二进制记录哈希；本地产物验证忽略规则。
4. 更新索引和引用，运行治理测试及 `git diff --check`。
5. 批量移动、取消跟踪或处理用户本地文件时，先提交逐文件清单并取得明确确认。
