# 042 / 045 路径迁移记录

状态：`current`（迁移审计）  
执行日期：2026-07-16 至 2026-07-17  
批准依据：042 的 140 项清单确认，以及 045 的 1,127 项清单确认。045 确认明确包含 9 条 043 规格及日志、用户输入、持久状态、缓存和临时入口，并明确“不授权删除”。

完整逐文件源路径、目标路径、跟踪策略、迁移前哈希和回滚方式见 [042 清单](../../03-requirements/specs/042-repo-architecture-modernization/asset-migration-manifest.json)、[045 清单](../../03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json) 和 [2026-07-18 客户验证目录合并记录](customer-validation-merge-20260718.md)。本页记录最终维护路径；历史规格、清单、离线结果元数据和迁移前基线中的旧路径作为当时证据保留，不批量改写。

## 2026-07-18 客户调研与验证目录合并

`01-discovery/` 与 `05-validation/` 已合并为 `01-customer-validation/`。每个客户或项目仅保留 `customer-materials/`、`validation-plans/`、`validation-results/` 三个业务类别。下方 045 表格继续保留更早一轮迁移的历史路径，不代表当前写入位置。

## 045 最终生命周期映射

| 042 前或 042 中间路径 | 045 后权威路径 | 维护规则 |
| --- | --- | --- |
| `docs/architecture/`、`tools/repo-governance/` | `00-governance/architecture/`、`00-governance/repository-tools/` | 仓库治理、策略、测试和迁移历史统一归属治理阶段 |
| `docs/research/` 及客户原始分析 | `01-discovery/workpackages/` | 按客户调研或来源数据工作包组织输入、脚本和结论 |
| 根目录产品方向方案 | `02-solution-analysis/proposals/` | 只存过程方案、取舍和决策依据 |
| `docs/product/` | `03-requirements/product/` | PRD 与研发交底 |
| `docs/engineering/` | `03-requirements/rules/` | 算法、工艺、资源和工期规则 |
| `specs/` | `03-requirements/specs/` | Spec Kit 唯一规格根；编号和历史内容不变 |
| `backend/`、`frontend/`、`examples/`、Demo 工具 | `04-demo/backend/`、`04-demo/frontend/`、`04-demo/examples/`、`04-demo/tools/` | 主 Demo 与可复现样例 |
| 独立 JSON 展示器及固定结果查看器 | `04-demo/standalone/<workpackage>/` | 与主 Demo 解耦，按工作包声明输入、入口和结果 |
| 客户验证材料、分析脚本和验证结果 | `05-validation/workpackages/<workpackage>/` | 输入、脚本、结果分区，客户原始输入不得被清理 |
| 正式二进制、案例总结和 AI PPT 工具 | `06-delivery/deliverables/`、`06-delivery/case-studies/`、`06-delivery/presentations/` | 正式成果保留跟踪和哈希，生成器与成果关系显式登记 |
| 根日志、历史 `logs/` | `.local-data/logs/legacy-unclassified/` | 本地保留、忽略跟踪；后台新日志写 `.local-data/logs/<启动时间>/` |
| 本地 JSON/数据库配置 | `.local-data/state/` | 新路径优先；迁移期读取兼容由 `04-demo/backend/app/local_paths.py` 管理 |
| 缓存、临时文件、锁和可再生成物 | `.local-data/cache/`、`.local-data/tmp/`、`.local-data/locks/`、`.local-data/archive/rebuildable/` | 默认只 dry-run，保护资产永不进入清理候选 |
| `outputs/lugu-validation-20260715` | 根目录原位保留并登记 `retained-local-cache` | 外部依赖目录联接；045 不移动、不删除，后续需单独授权 |

045 没有删除动作。空旧目录也没有删除，而是移入 `.local-data/archive/migration-empty-shells/`；所有清理工具默认 dry-run。

## 042 中间映射

| 042 前历史路径 | 042 中间路径 | 042 当时策略 |
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

- `03-requirements/specs/001`～`043` 内仍出现的 `specs/`、`docs/`、`backend/`、`frontend/`、`netlify/demo-functions/api.mts`、根样例 Excel 和旧输出目录，描述的是对应规格实施时的真实位置，保留原文。
- `repository-inventory.json` 和迁移清单中的旧路径是迁移前基线，不属于失效的当前运行说明。
- 离线结果 JSON 内的绝对 `workbook_path` 是历史运行元数据，不参与当前默认样例定位。
- 042 表格中的 `docs/`、`tools/`、`deliverables/` 和 `artifacts/` 是 2026-07-16 的中间落点；维护者必须以本页 045 最终映射、根 README 和阶段 README 为准。

## 回退

逐文件回退使用对应清单的 `rollback` 字段，按 045 批次反向回到 042 中间路径后，才可按 042 清单继续回退。正式交付物和样例回退前必须先复核 SHA-256；本地产物回退只移动本地文件，不改变 Git。任何删除仍需新的明确授权。
