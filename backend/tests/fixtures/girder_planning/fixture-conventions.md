# 架梁专项黄金夹具约定

- 文件名使用 `<类别>-<场景>-v<版本>.json`，类别为 `legacy`、`rule-change` 或 `performance`。
- `fixture-manifest.json` 是唯一清单，必须登记来源、脱敏状态、预期结果和差异类型。
- 真实项目数据必须脱敏；不得保存人员、合同金额、坐标原值或任何密钥。
- `legacy_parity` 夹具要求未变规则一致；`confirmed_rule_change` 夹具允许且必须解释已确认差异。
- 日期统一使用 `YYYY-MM-DD`，里程统一使用米，数量不得使用格式化字符串。
