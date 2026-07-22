# 快速验证：工点资源排除预制梁班组

## 定向自动化验证

在仓库根目录执行：

```powershell
node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs
npm.cmd run typecheck
npm.cmd run build
python 00-governance/repository-tools/validate_docs.py
```

预期：全部命令退出码为 0；资源领域测试证明目录和结构匹配均排除 `precast_beam_team`，既有其他资源断言继续通过。

## 页面场景

1. 选择包含预制梁构件的桥梁工点。
2. 确认默认建议没有“预制梁班组”及 `precast_beam_team`。
3. 展开“从资源目录补充”，确认没有对应选项。
4. 确认桩基、承台、墩柱、盖梁等该工点已有结构资源仍正常显示。
5. 不配置梁场专项，重新进入资源页，确认系统不会恢复预制梁班组兜底项。
