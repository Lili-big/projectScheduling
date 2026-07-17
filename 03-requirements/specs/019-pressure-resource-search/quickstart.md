# Quickstart：新增资源压力工期搜索验证

## 前置条件

- 已安装后端依赖并可运行 pytest。
- 使用当前仓库根目录作为工作目录。
- 当前工作区已有未提交改动时，实施前必须先确认不会覆盖无关文件。

## 验证场景 1：当前资源超期后产生新增候选

目标：证明固定资源精排可用但目标未满足时，资源建议会按压力目标继续搜索，不再反复返回当前下限。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q -k "pressure_resource"
```

期望：
- 主结果保留当前资源排程。
- `resource_recommendation_status` 在候选成功时为 `recommended_resources_verified`。
- `pressure_search_attempts` 至少包含 1 轮。
- 至少一个候选资源的 `added_quantity > 0`。
- 成功候选满足原始目标。

## 验证场景 2：返回当前下限时继续压缩

目标：证明当容量模型返回当前资源数量时，系统继续下一轮压力搜索。

期望：
- 第 1 轮 `candidate_quantities` 等于 `search_lower_bounds`。
- 第 1 轮 `stop_reason` 表示 `same_as_lower_bounds`。
- 第 2 轮使用更短的 `pressure_target_days`。

## 验证场景 3：关键路径边界阻止过度压缩

目标：证明内部压力目标不会早于工艺关键路径理论最短工期。

期望：
- 当压缩目标触达关键路径边界时，`clamped_by_critical_path` 为 `true`。
- 若仍无可验证候选，资源建议状态不应显示成功推荐。
- 诊断说明停止原因为关键路径边界或不可压缩。

## 验证场景 4：候选必须回到原始目标验收

目标：证明内部压力目标只用于搜索，不能作为成功推荐依据。

期望：
- 容量模型候选满足内部压力目标但完整精排不满足原始目标时，`resource_recommendation_status` 不是 `recommended_resources_verified`。
- 结果保留当前资源主排程，并记录候选验证失败。

## 建议完整验证

后端：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q -k "fixed_resource or min_resources or pressure_resource"
.\.venv\Scripts\python.exe -m py_compile backend\app\scenario.py backend\app\solver.py backend\tests\test_scheduler.py
```

前端如有展示改动：

```powershell
cd frontend
npm run build
```

## 通过标准

- 所有新增测试通过。
- 既有固定资源成功分支不进入资源建议。
- 既有资源上限不足、关键路径不可行、未确认状态仍保持可解释。
- 页面能区分原始目标和内部压力目标。
