# 快速验证：AI 多方案按工点推进资源

## 前置条件

- 使用包含至少两个桥梁工点 A、B 的项目场景。
- A、B 分别存在至少一个启用的 `WORKPOINT_EXCLUSIVE` 本地资源池。
- 至少存在一个覆盖 A、B 的 `PROJECT_SHARED` 池。
- 记录初始化前所有资源池的完整 JSON，作为逐池冻结基线。

## 1. 后端定向验证

```powershell
python -m pytest 04-demo/backend/tests/test_ai_resource_scheduling_assistant.py 04-demo/backend/tests/test_assistant_routes.py 04-demo/backend/tests/test_contracts_assistants.py -q
```

预期：

- 未传工点、未知工点、无可调本地资源返回 422。
- 为 A 生成的三方案都携带 A 的稳定身份。
- 只有 A 的本地池数量可产生经济、平衡、抢工差异。
- B 的本地池及所有共享池与输入逐池完全一致。
- 尝试更新 B 或共享池被拒绝。
- 求解结果仍包含 A、B 的全部项目任务。
- 不同目标工点的方案不能混合比较或推荐。

## 2. 前端契约与类型验证

```powershell
npm.cmd run typecheck
npm.cmd --workspace 04-demo/frontend test
```

预期：

- 未选择工点时不发初始化请求。
- 工点切换清空旧方案、结果、详情、推荐和基准状态。
- 迟到响应不能覆盖当前工点。
- 方案卡只生成目标工点本地资源输入行。
- 同名工点仍以稳定身份正确选择。

## 3. 生产构建

```powershell
npm.cmd run build
```

预期：TypeScript 与 Vite 构建通过，AI 多方案页面可正常打包。

## 4. 手工闭环

1. 打开“AI多方案比选”，确认工点下拉初始未选择，“生成三方案”不可用。
2. 选择工点 A，生成三方案。
3. 核对每张方案卡只显示 A 的本地资源，并显示“全项目排程”说明。
4. 分别求解经济、平衡、抢工方案，进入详情确认任务同时包含 A、B。
5. 生成指标对比与 LLM 推荐，确认指标仍为全项目口径。
6. 切换为 B，确认 A 的方案、结果、详情和推荐全部清空。
7. 为 B 重新生成，确认任何迟到的 A 响应未覆盖 B。

## 5. 契约与文档校验

```powershell
python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path(r'03-requirements/specs/053-ai-workpoint-resource-comparison/contracts/ai-workpoint-resource-comparison.openapi.yaml').read_text(encoding='utf-8')); print('openapi yaml ok')"
python 00-governance/repository-tools/validate_docs.py
git diff --check
```

预期：YAML 可解析、文档校验通过、无空白错误。

## 不变量核对

- `pool.id` 跨输入、三方案、求解结果保持不变。
- 同类型多池不按 `type` 合并。
- 共享池数量、上限、状态和范围不变。
- 目标工点数量始终为非负整数且不超过逐记录 `max_quantity`。
- 求解目标、15 秒预算、任务生成和全项目指标未改变。
