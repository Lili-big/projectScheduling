# 交付物构建器

本目录只保存可复用的交付物构建与校验脚本；正式交付物位于根 `deliverables/`，预览和检查中间件位于本地 `artifacts/`。

- `lugu-report/`：泸古项目报告提取、构建和检查脚本。
- `lugu-validation/`：泸古验证工作簿构建与复核脚本。

构建器不应再把结果写回 `outputs/`。工作簿脚本默认写入 `deliverables/validation/lugu/`，验证迁移或开发变更时应使用 `--output` 指向临时目录，复核通过后再决定是否替换正式交付物。

```powershell
node .\tools\delivery-builders\lugu-validation\build_validation_workbook.mjs --output <临时工作簿路径>
node .\tools\delivery-builders\lugu-validation\verify_validation_workbook.mjs --input <临时工作簿路径>
```
