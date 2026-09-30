# 快速验证指南：076-pavement-shift-productivity

日期：2026-09-29。实施完成后按本指南验证端到端行为；字段与公式定义见 [data-model.md](../data-model.md)，契约面见 [contracts/backend-frontend-contract-changes.md](./contracts/backend-frontend-contract-changes.md)。

## 前置条件

- 仓库根 `.venv` 可用（含 ortools ≥9.10）；前端依赖已安装（`npm install`）。
- 命令均在仓库根目录执行。

## 1. 自动化测试（SC-001/SC-002 核心证据）

```powershell
# 后端定向（班制新增用例）+ 既有全量回归（既有断言零修改是验收项）
.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_shift.py -q
.venv\Scripts\python.exe -m pytest 04-demo/backend/tests -q

# 前端定向 + 全量
npm --workspace 04-demo/frontend test
npm run typecheck && npm run build
```

**期望**：全部通过；`test_pavement_shift.py` 覆盖 SC-001 四个数值场景、无配置逐位一致、区间校验错误码、指纹失效、窝工共存。

## 2. 数值验收样例（SC-001）

统一输入：基准工效 1000m²/天、某结构层工程量 8000m²、计划开始日 2026-07-01、班制区间 `{2026-07-01 ~ 2026-09-30, 1}` + `{2026-10-01 ~ 空, 2}`。

| 场景 | 开工日 | 期望工期 | 拆分 |
| --- | --- | --- | --- |
| 无班制配置 | 任意 | 8 天 | 单班 8 天 |
| 双班内开工 | 2026-10-05 | 4 天 | 双班 4 天 |
| 跨界开工 | 2026-09-25 | 7 天 | 单班 6 + 双班 1 |
| 单班内开工 | 2026-09-01 | 8 天 | 单班 8 天 |

## 3. 页面端到端（用户故事 1–3）

1. 启动后端与前端（按 `04-demo/runtime/README.md`）。
2. 路面工作区 → 工序/逻辑页：在路面设置中新增班制区间（如 2026-10-01 起、结束留空、双班），保存。
3. 结果页"按固定机组求解"：确认结果任务工期缩短，任务详情显示单/双班拆分，横道图标注双班区间，方案摘要资源假设含班制说明。
4. 修改区间起始日并保存：确认结果立即出现"历史结果"提示；重新求解后提示消失。
5. 清空全部区间并求解：结果与未配置时一致。

## 4. 边界与异常（对应 spec"边界与异常场景"）

- 配置起始日晚于结束日 / 两条同起始日 / 相互重叠：生成与求解均报 `PAVEMENT_SHIFT_INVALID`，不进入求解（结果页诊断可见）。
- 未配置班制执行窝工优化：行为与现状一致。
- 配置班制后先求解、再改班制、直接点"优化窝工"：应 422 `PAVEMENT_BASELINE_OUTDATED`，要求重新求解。

## 5. 门禁

```powershell
npm.cmd run verify:architecture   # 架构基线（前后端 fixture 已重新捕获）与治理
npm.cmd run verify                # 发布级全量（实施收尾时）
```
