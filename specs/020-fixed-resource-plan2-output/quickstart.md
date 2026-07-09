# Quickstart：固定资源方案2输出提示验证

## 前置条件

- 位于仓库根目录。
- 已安装后端和前端依赖。
- 不需要启动服务即可完成后端回归测试；前端构建用于检查类型与打包。

## 场景 1：当前资源目标失败但方案1保留

目的：验证当前资源可查看但硬里程碑未满足时，方案1仍输出。

验证方式：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
```

预期结果：
- 固定资源求解结果包含当前资源主排程。
- `target_achievement.business_success=false`。
- `alternative_output_status` 表达新增资源方案是否输出。
- 当前资源任务、资源分配、里程碑迟延仍可查看。

## 场景 2：新增资源成功时输出方案2

目的：验证当前资源目标失败后，新增资源候选成功时进入方案2。

验证方式：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
```

预期结果：
- `alternative_results` 包含一个新增资源候选。
- 方案1为当前资源，方案2为新增资源候选。
- 方案2有独立任务、资源、里程碑和诊断。

## 场景 3：新增资源失败时提示方案2未输出

目的：验证新增资源分支无可展示候选时，系统只返回方案1并提示方案2未输出。

验证方式：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q
```

预期结果：
- `alternative_results` 为空。
- `alternative_output_status=not_output`。
- 提示文案包含“方案2未输出”或等价明确提示。
- 方案1仍保留当前资源的任务和里程碑迟延。

## 前端构建验证

```powershell
npm.cmd run build
```

预期结果：
- 构建通过。
- 方案输出区在无方案2时不出现空切换入口。
- 页面诊断或方案输出区能显示方案2未输出提示。
