# 研究结论：工点资源排除预制梁班组

## 决策：扩展既有统一排除集合

**决策**：将 `precast_beam_team` 加入 `04-demo/frontend/src/domain/constants.ts` 的 `excludedResourceCatalogTypes`。

**理由**：050 的 `resourceCatalogProjection` 与 `workpointResourceTypeProjection` 已共同调用该集合。一处变更可以同时保证：预制梁构件不产生工点资源建议、完整补充目录不出现该类型，同时不影响预制梁工艺和求解器。

**评估的替代方案**：

- 只在 `ResourcesTab.tsx` 隐藏行：会让领域目录仍包含该类型，并产生页面与其他调用方不一致。
- 删除 `precast_beam` 的工艺资源映射：会扩大到任务和求解语义，超出用户仅调整工点资源边界的请求。
- 删除历史配置：属于不可逆数据清理，用户没有授权，且当前目标不需要。

## 无阻塞未知项

`beam_erection_team` 是架梁施工资源，不是预制梁生产能力，保持现状。梁场能力模块不在本期建设范围。
