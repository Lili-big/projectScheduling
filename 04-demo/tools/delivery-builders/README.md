# 交付物构建器迁移索引

本目录仅保留 042 中间结构的兼容说明，不再承载构建脚本。正式交付物位于 `06-delivery/deliverables/`；脚本跟随调研或验证工作包；预览和检查中间件位于 `.local-data/archive/rebuildable/`。

- 泸古调研报告：`01-customer-validation/lugu/customer-materials/_scripts/`。
- 泸古验证工作簿：`01-customer-validation/lugu/validation-plans/_scripts/`。

构建器不得把结果写回根 `outputs/`。验证迁移或开发变更时使用 `.local-data/archive/rebuildable/`，复核通过后再决定是否替换正式交付物。

```powershell
node .\01-customer-validation\lugu\validation-plans\_scripts\build_validation_workbook.mjs --output <临时工作簿路径>
node .\01-customer-validation\lugu\validation-plans\_scripts\verify_validation_workbook.mjs --input <临时工作簿路径>
```
