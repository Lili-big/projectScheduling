# 仓库治理工具

本目录提供 042 架构迁移的无第三方依赖检查器：

- `inventory_repository.py`：生成资产、跟踪状态、引用和二进制哈希清单。
- `validate_dependencies.py`：检查后端 contracts/scheduling 和前端 contracts/domain/features 的依赖方向。
- `validate_repository.py`：检查根目录增量、误跟踪本地文件及 Python/npm 依赖基线。
- `validate_docs.py`：检查入口及架构文档内部链接和已记录 API 路径。
- `build_asset_migration_manifest.py`：生成受跟踪资产和根目录本地日志的逐文件迁移清单、哈希及回滚方式。
- `tests/`：检查根目录、日志落点、文档索引、迁移映射和正式交付物哈希。

统一入口：

```powershell
npm.cmd run verify:architecture
```

该命令只运行架构与仓库门禁，不替代后端全量测试、前端 Node 测试、TypeScript 检查或生产构建。
