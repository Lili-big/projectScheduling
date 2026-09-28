# 最小验证指南

前提：仓库现有.venv、node_modules；复用已有8000服务，后台操作遵守04-demo/runtime/README.md。

1. `.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_master.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_layer_template.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_api.py -q`
   覆盖按米空厚度或已有非正值均不参与计算校验、其他单位原规则、几何量不一致、沥青FS+7、工期1001/1000向上取整为2天；合成有机组可行、零机组明确失败；既有停用恢复回归。
2. `node --test 04-demo/frontend/tests/pavementVisualization.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs`；验证spec SC-001、独立资源、并集、边界/缺失、更新与静态渲染顺序。底部清理和错误承接属于暂缓的T005b，随该任务补充验证。
3. `npm.cmd run build`；包含TypeScript检查。
4. 历史厚度验收复用T001/T002证据：曾生成95任务、19条FS+7，厚度空且零沥青机组报缺资源。用户随后停用全部19条沥青，当前图表验收使用19个在用施工段、76道任务，不为复现历史条件改回主数据或资源配置。
5. 以有限预算的同次真实结果验证图/资源筛选/区间详情/键盘/最长空闲及窄屏滚动，截屏放本轮.local-data/logs/；多实例、未分配资源、异常和快照替换使用第2项合成样例。不改变用户输入或保存配置；另开验证页，保留用户已有未保存页面。
6. `.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py`、`validate_lifecycle_workspace.py`、`validate_docs.py`各一次。记录既有历史引用失败，不扩展修复。

改动导致失败仅复跑受影响项。完成后把退出结果、截图、变更范围和剩余真实资源配置限制记入tasks；不对当前数据启动不限时试算。

2026-09-27历史厚度批次：T001/T002后端定向87项通过（首轮86项通过，修正新增测试调用后该1项通过）；当时真实95任务生成且无厚度错误，仍有未投入沥青机组的资源不足提示。

2026-09-27资源图批次：21项前端测试通过，构建通过；真实76任务、256天结果显示作业196天、转场56天、期间空闲4天、最长1天、作业率76.6%。宽屏1280和窄屏640的内部滚动、名称可见、键盘区间详情与最长空闲定位通过，原视口已恢复。证据见 `.local-data/logs/20260927-223850-pavement-resource-timeline/`。
