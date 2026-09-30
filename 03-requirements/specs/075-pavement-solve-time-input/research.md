# 研究结论

## 已解决的唯一阻塞问题

仅在界面修改 scenario.time_limit_seconds，会同时改变前端方案指纹和后端生成输入；现有窝工准备步骤对生成输入全量比较，且校验完整指纹，因此不能在原方案上继续优化。

**证据**：`04-demo/frontend/src/app/workflows/scenarioWorkflow.ts`、`04-demo/backend/app/scheduling/application/pavement.py` 的 prepare_pavement_idle、`04-demo/backend/app/scheduling/solver/strategies/pavement.py` 的 schedule_fingerprint/validate_idle_baseline。

**决策**：页面维护本轮预算；普通求解使用请求副本中的既有时限，窝工请求增加独立可选预算，基准仍使用原完整身份校验。

**理由**：支持用户在原方案上调整优化时间，不改变工期上限或任何业务校验；不需要修改指纹算法或迁移历史结果。

**评估的替代方案**：仅加输入框会使改预算后必须重新做工期求解；从所有指纹中排除预算则需要改动更多基准识别和流式校验。两者不采用。

其他部分沿用已有实现，无新增研究决策、依赖或外部调研。
