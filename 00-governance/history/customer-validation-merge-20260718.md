# 客户调研与验证目录合并记录（2026-07-18）

## 决策与确认

- 用户确认将 `01-discovery/` 与 `05-validation/` 合并为 `01-customer-validation/`。
- 客户或项目目录只保留 `customer-materials/`、`validation-plans/`、`validation-results/` 三个业务类别。
- 脚本进入对应类别的 `_scripts/`；预览、检查数据和本地数据库进入 `.local-data/archive/rebuildable/customer-validation/`。
- 迁移只移动文件，不删除客户原始资料或本地真实输入。

## 阶段入口

| 原路径 | 当前路径 |
| --- | --- |
| `01-discovery/README.md` | `01-customer-validation/README.md` |
| `05-validation/README.md` | 合并到 `01-customer-validation/README.md` |

## 泸古项目

### 客户资料

| 原文件 | 当前文件 |
| --- | --- |
| `lugu-source-data-analysis/inputs/泸古1标架梁工点导入模板.xlsx` | `lugu/customer-materials/泸古1标架梁工点导入模板.xlsx` |
| `lugu-customer-research/results/泸古项目7月15日上午调研验证记录_20260715.docx` | `lugu/customer-materials/泸古项目7月15日上午调研验证记录_20260715.docx` |
| `lugu-customer-research/results/泸古项目7月16日前期工期策划思路分析_20260715.docx` | `lugu/customer-materials/泸古项目7月16日前期工期策划思路分析_20260715.docx` |
| `lugu-source-data-analysis/results/bridge_progress_profile.json` | `lugu/customer-materials/bridge_progress_profile.json` |
| `lugu-source-data-analysis/results/bridge_schedule_structure.json` | `lugu/customer-materials/bridge_schedule_structure.json` |
| `lugu-customer-research/scripts/build_planning_logic_report.py` | `lugu/customer-materials/_scripts/build_planning_logic_report.py` |
| `lugu-customer-research/scripts/build_report.py` | `lugu/customer-materials/_scripts/build_report.py` |
| `lugu-customer-research/scripts/check_planning_logic_report.py` | `lugu/customer-materials/_scripts/check_planning_logic_report.py` |
| `lugu-customer-research/scripts/extract_planning_transcript.py` | `lugu/customer-materials/_scripts/extract_planning_transcript.py` |
| `lugu-source-data-analysis/scripts/analyze_bridge_schedule_workbook.py` | `lugu/customer-materials/_scripts/analyze_bridge_schedule_workbook.py` |

### 验证计划

| 原文件 | 当前文件 |
| --- | --- |
| `lugu-customer-research/inputs/泸古项目客户访谈提纲_20260715.md` | `lugu/validation-plans/泸古项目客户访谈提纲_20260715.md` |
| `lugu-validation-material/plans/泸古项目客户验证计划_20260715.md` | `lugu/validation-plans/泸古项目客户验证计划_20260715.md` |
| `lugu-validation-material/plans/客户价值验证调研提纲记录表_20260717.xlsx` | `lugu/validation-plans/客户价值验证调研提纲记录表_20260717.xlsx` |
| `lugu-validation-material/plans/客户价值验证调研提纲记录表_总进度计划策划与多方案比选_v2_20260717.xlsx` | `lugu/validation-plans/客户价值验证调研提纲记录表_总进度计划策划与多方案比选_v2_20260717.xlsx` |
| `lugu-validation-material/scripts/build_validation_workbook.mjs` | `lugu/validation-plans/_scripts/build_validation_workbook.mjs` |
| `lugu-validation-material/scripts/verify_validation_workbook.mjs` | `lugu/validation-plans/_scripts/verify_validation_workbook.mjs` |

### 验证结果

| 原文件 | 当前文件 |
| --- | --- |
| `lugu-plan-granularity/results/new_total_plan_profile.json` | `lugu/validation-results/new_total_plan_profile.json` |
| `lugu-plan-granularity/results/plan_version_comparison.json` | `lugu/validation-results/plan_version_comparison.json` |
| `lugu-plan-granularity/results/泸古项目计划管理方式变化验证记录_20260716_v3.docx` | `lugu/validation-results/泸古项目计划管理方式变化验证记录_20260716_v3.docx` |
| `lugu-plan-granularity/results/泸古项目计划粒度验证记录_20260716.docx` | `lugu/validation-results/泸古项目计划粒度验证记录_20260716.docx` |
| `lugu-plan-granularity/results/泸古项目计划粒度验证记录_20260716_v2.docx` | `lugu/validation-results/泸古项目计划粒度验证记录_20260716_v2.docx` |
| `lugu-validation-material/project-master/results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx` | `lugu/validation-results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx` |
| `lugu-validation-material/project-master/results/泸古TJ-1标统一主数据_mapping-report.json` | `lugu/validation-results/泸古TJ-1标统一主数据_mapping-report.json` |
| `lugu-plan-granularity/scripts/build_business_validation.py` | `lugu/validation-results/_scripts/build_business_validation.py` |
| `lugu-plan-granularity/scripts/build_plan_granularity_validation.py` | `lugu/validation-results/_scripts/build_plan_granularity_validation.py` |
| `lugu-plan-granularity/scripts/check_business_validation.py` | `lugu/validation-results/_scripts/check_business_validation.py` |
| `lugu-plan-granularity/scripts/check_plan_granularity_validation.py` | `lugu/validation-results/_scripts/check_plan_granularity_validation.py` |
| `lugu-plan-granularity/scripts/compare_plan_versions.py` | `lugu/validation-results/_scripts/compare_plan_versions.py` |
| `lugu-plan-granularity/scripts/inspect_new_plan_rows.py` | `lugu/validation-results/_scripts/inspect_new_plan_rows.py` |
| `lugu-validation-material/project-master/scripts/build_lugu_project_master.mjs` | `lugu/validation-results/_scripts/build_lugu_project_master.mjs` |
| `lugu-validation-material/project-master/scripts/inspect_source_workbooks.mjs` | `lugu/validation-results/_scripts/inspect_source_workbooks.mjs` |

### 可再生成本地文件

以下文件从 `lugu-validation-material/project-master/results/` 移至 `.local-data/archive/rebuildable/customer-validation/lugu/project-master/`：

- `bridge-progress-cells.json`
- `bridge-progress-preview.png`
- `bridge-progress-sheets.ndjson`
- `bridge-progress-summary.ndjson`
- `lugu-project-master-acceptance.db`
- `preview-填写说明.png`
- `preview-工点信息.png`
- `preview-构件参数.png`
- `preview-结构物信息.png`
- `workpoints-cells.json`
- `workpoints-preview.png`
- `workpoints-sheets.ndjson`
- `workpoints-summary.ndjson`
- `泸古TJ-1标统一主数据_inspect.ndjson`
- `泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx.inspect.ndjson`

## 其他项目

- 基建版本历史资料：11份 `D001`～`D011` PDF 和 `source-map.local.json` 移至 `infrastructure-version-2026q2/customer-materials/`；`asset-index.md` 移至 `validation-results/`。
- 垫丰武 TJ03：4份 `V001`～`V004` PDF 和 `source-map.local.json` 移至 `dianfengwu-tj03/customer-materials/`；`asset-index.md` 移至 `validation-results/`。
- JSON 排程评审：真实 JSON 移至 `json-schedule-review/customer-materials/`；HTML、报告 JSON 移至 `validation-results/`；两个入口脚本移至 `validation-results/_scripts/`。
- AI 助手：两份验证说明移至 `ai-assistants/validation-results/`。

## 回退边界

如需回退，只按本记录反向移动；不得复制形成两份权威文件。`.local-data` 中的可再生成文件不自动恢复为 tracked，客户本地资料回退前必须再次核对脱敏索引和 SHA-256。
