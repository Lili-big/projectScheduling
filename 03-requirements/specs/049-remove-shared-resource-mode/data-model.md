# 数据模型：移除资源共享模式

## 1. 历史共享资源记录

旧项目中满足以下任一条件的 `ResourcePool`：

- `scope_mode == "PROJECT_SHARED"`；
- `scope_mode` 缺失，按现有契约默认解析为 `PROJECT_SHARED`。

这些记录仅作为清理输入，不进入当前有效资源集合。其数量、上限和范围不转移到工点资源。

## 2. 工点独享资源池

当前唯一有效的项目资源记录：

- `scope_mode == "WORKPOINT_EXCLUSIVE"`；
- 直接记录必须具有非空 `workpoint_id`；
- 同一 `(workpoint_id, type)` 最多一条；
- `quantity`、`max_quantity`、`enabled`、日历和成本字段沿用现有校验。

旧式 `WORKPOINT_EXCLUSIVE` 记录缺少直接 `workpoint_id` 时，继续根据权威工点集合和 override 按 048 规则展开，再进入当前有效集合。

## 3. 当前有效资源集合

完成加载/保存标准化后的 `resource_pools`：

- 只包含工点独享资源池；
- 允许为空数组；
- 用于页面、持久化返回、正常项目任务生成、求解、AI 输入和场景指纹；
- 不包含共享数量、共享范围或共享池身份。

## 4. 状态转换

### 本地配置加载

```text
原始 JSON
  -> Pydantic 校验
  -> legacy 独享池无损展开
  -> 删除 PROJECT_SHARED 记录
  -> 校验本地池 ID 与 (workpoint_id,type) 唯一性
  -> 若发生删除，原子写回清理后的本地配置
  -> 当前有效资源集合
```

### 本地配置保存

```text
请求 resource_pools（允许空）
  -> 校验并展开合法 legacy 独享池
  -> 删除 PROJECT_SHARED 记录
  -> 原子写入当前配置
  -> 返回只含工点独享池的资源集合
```

### 正常项目计算

```text
当前有效资源集合
  -> 前端场景标准化再次只保留工点独享池
  -> 现有任务生成/求解入口
```

求解器对绕过项目数据边界而显式构造的共享输入保持既有行为。

## 5. 数据完整性与失败行为

- 清理写回复用现有同目录临时文件和原子替换，不允许部分写入。
- JSON 解析、模型校验或写入失败继续返回 `LocalScenarioConfigError`，HTTP 层映射为 503。
- 清理不得改变非资源配置和工点独享池字段。
- 历史排程快照、保存结果、验证证据不参与状态转换。
