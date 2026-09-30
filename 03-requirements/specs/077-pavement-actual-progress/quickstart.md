# 验证指南：路面实际进度统计

当前为设计文档；以下新增测试和页面在实施后执行。先满足用户确认门禁，再实施、验证，不在规划阶段写入真实数据。

## 环境与隔离

在仓库根目录运行，使用现有 `.venv` 和Node依赖。后端测试通过临时SQLite数据库及注入ProjectMasterService构造样例，不修改用户主数据库、资源和配置。样例工序设计长度1790m，宽厚从夹具主数据读取，其中另设宽厚缺失工序。

浏览器验收使用单独测试项目/隔离临时数据库和新页签，关闭后保留用户原页及未保存输入。需启动测试服务时遵循 `04-demo/runtime/README.md`，日志放 `.local-data/logs/`；所有可持久状态只放 `.local-data/state/` 的测试专用位置。不要使用生产项目填测试数字。

## 定向自动验证

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo/backend/tests/test_pavement_progress.py 04-demo/backend/tests/test_pavement_progress_schema.py 04-demo/backend/tests/test_project_master_repository.py 04-demo/backend/tests/test_project_master_api.py -q
node --test 04-demo/frontend/tests/pavementProgress.test.mjs 04-demo/frontend/tests/projectMasterApi.test.mjs 04-demo/frontend/tests/pavementTaskPreview.test.mjs
npm run build
```

每个相关批次只运行一次；失败修复后只重跑受影响检查。预期包括数据库重建读取、旧版本升级、接口字段/状态码、历史及并发完整性、表格投影、每日量精度与月历边界。前端构建已含类型检查，不重复运行同一全量检查。

## 浏览器验收

1. 无求解结果进入路面“计划执行→实际进度统计”；与任务视图对照ID/名称/顺序/启停，施工段父行可折叠。桥梁无新菜单。
2. 左侧为施工段和工序及只读主数据/统计，右侧所选月份日期。宽厚缺失为“—”，空日格保持中性。改工效计量单位不改本页长度口径。
3. 9月1日填300、9月2日填450，累计750、剩余1040；10月1日填100，累计850、剩余940；返回9月、折叠/展开或离开菜单返回，数值和草稿不丢。
4. 将300改320后剩余920；清空450后剩余1370；输入0单独保留。保存后重新加载确认，服务重建读回由临时库自动测试覆盖。
5. 将累计改为1800，剩余-10、标记超量10m；允许保存且读回一致。0.1+0.2显示0.3。负数、非法小数、无效日期被明确拒绝；空白不是错误。
6. 查看约100工序×31日样例，在约1700px及1024px宽视口检查表头/左列固定、横纵滚动、单元格可达及键盘输入。截图仅为隔离样例证据。
7. 双页面同revision先后保存：第二个409并保留草稿；重读显示已保存值与本地值待核对，不能自动覆盖。断网/503不显示成功，草稿可重试；保存中禁编。
8. 主数据改名/改长度并发版后每日量保持，按新长度算剩余；停用记录进入历史只读，重新启用同ID恢复，不同ID不继承。存在本地主数据草稿时先要求处理主数据，避免填报错误版本。
9. 保持已求解方案进入进度表保存，确认方案、资源、工效、班制未改；没有产生新主数据版本。刷新有未保存提醒，镜像路径明确不支持。

## 资产、架构及完成证据

按现有架构捕获脚本帮助更新并核对仅与新端点/模块相关的两份基线，再执行对应check；不覆盖其他功能已有合理修改。新增文档/代码资产执行：

```powershell
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_repository.py
.\.venv\Scripts\python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py --json
```

将实际命令、退出结果、已知无关失败及浏览器证据路径写入 [tasks.md](./tasks.md)。不通过清理脚本删除状态或日志，不把未执行的检查写成通过。

## 实际使用前

读取实际PROJECT_MASTER_DB_PATH，用SQLite backup API备份到 `.local-data/state/` 的带时间戳文件，再由新版本正常初始化执行增量升级。先验证临时库；失败保留原库和备份，不自动覆盖、降级或抛弃已录进度。详细模型见 [data-model.md](./data-model.md)。
