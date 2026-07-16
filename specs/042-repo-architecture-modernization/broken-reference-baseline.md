# 失效引用与陈旧入口基线

## 扫描结果（2026-07-16）

- 对 `docs/**/*.md` 和 `specs/**/*.md` 的显式 Markdown 相对链接扫描：0 个目标缺失。
- `agent.md` 存在 3 处当前错误路径：`netlify/functions/api.mts`；真实位置为 `netlify/demo-functions/api.mts`，且当前未接入 `netlify.toml`。
- README/agent 对架梁专项、计划管控、进度预测和资源助手的当前入口覆盖不足，属于陈旧导航，不是缺失文件。
- 历史规格大量引用当时的大文件路径（`models.py`、`scenario.py`、`solver.py`、`App.tsx`）；这些是历史实现记录。042 通过兼容 façade 保持路径，不批量改写历史 spec。

## 分类

| 类型 | 处理 |
| --- | --- |
| 真实错误 | 在 T027～T029 修正当前 README/agent/docs；自动文档门禁阻止复发 |
| 历史缺失 | 当前显式链接扫描无此类；以后标记 `missing_source`，不伪造文件 |
| 规划目标 | `041` 未完成项和 `042` 目标明确标为 draft/active_partial，不写成现状 |
| 历史路径 | 保留历史 spec；旧代码入口由兼容 façade 维持，最终所有权由架构地图解释 |

## 不在本批处理

根目录历史文档、`docs/` 生成结果、Office 临时锁文件和参考工具的物理移动属于资产批次，必须先提供逐文件清单并取得用户第二次明确确认。
