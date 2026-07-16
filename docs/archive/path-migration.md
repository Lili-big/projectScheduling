# 042 路径迁移记录

状态：`current`（迁移审计）  
执行日期：2026-07-16  
批准依据：用户明确确认“按更新后的 140 项资产迁移清单全部执行”。

完整逐文件源路径、目标路径、跟踪策略、迁移前哈希和回滚方式见 [`asset-migration-manifest.json`](../../specs/042-repo-architecture-modernization/asset-migration-manifest.json)。本页只记录当前维护者需要使用的路径映射；历史 specs 中的旧路径作为当时实施证据保留，不批量改写。

| 历史路径 | 当前路径 | 当前策略 |
| --- | --- | --- |
| 根目录 3 份产品方案 | `docs/product/` | 保持跟踪 |
| `docs/` 产品/页面文档 | `docs/product/` | 保持跟踪 |
| `docs/` 算法/规则交底 | `docs/engineering/` | 保持跟踪 |
| `docs/` 验证材料 | `docs/validation/` | 保持跟踪 |
| `docs/` 调研材料 | `docs/research/` | 保持跟踪 |
| `docs/AI驱动Demo快速验证与研发交付案例*` | `docs/archive/application-case/` | 保持跟踪，按 current/superseded 状态索引 |
| `docs/*viewer*` 与配套 JSON | `examples/result-viewer/` | 保持跟踪，作为离线可复现实例 |
| `ai-ppt-system/` 源码和配置 | `tools/ai-ppt-system/` | 保持跟踪 |
| `ai-ppt-system/output/` | `artifacts/ai-ppt-system/output/` | 本地保留，取消跟踪 |
| `netlify/demo-functions/` | `tools/demo-api-mirror/` | 保持跟踪，不参与部署 |
| `outputs/` 构建/校验脚本 | `tools/delivery-builders/` | 保持跟踪 |
| `outputs/` 正式 XLSX | `deliverables/` | 保持跟踪并校验 SHA-256 |
| `outputs/` 预览、检查结果和临时锁 | `artifacts/lugu-validation/` | 本地保留，取消跟踪 |
| 根 `渠溪河特大桥结构设计表.xlsx` | `examples/bridge-import/渠溪河特大桥结构设计表.xlsx` | 保持跟踪；读取器保留旧根路径兼容 |
| 根目录 16 个 `*.log` | `.local-data/logs/legacy/` | 仅本地移动，不删除、不跟踪 |
| `.netlify-cli-runtime/` 已跟踪配置 | `artifacts/netlify-cli/` | 本地保留，取消跟踪 |

## 历史引用解释

- `specs/001`～`041` 中的 `netlify/demo-functions/api.mts`、根样例 Excel 和旧输出目录引用，描述的是对应规格实施时的真实位置，保留原文。
- `repository-inventory.json` 和迁移清单中的旧路径是迁移前基线，不属于失效的当前运行说明。
- 离线结果 JSON 内的绝对 `workbook_path` 是历史运行元数据，不参与当前默认样例定位。

## 回退

逐文件回退使用迁移清单的 `rollback` 字段。正式交付物和样例回退前必须先复核 SHA-256；取消跟踪的本地产物回退时需要同时恢复原路径和 Git 跟踪状态。根日志回退只移动本地文件，不改变 Git。
