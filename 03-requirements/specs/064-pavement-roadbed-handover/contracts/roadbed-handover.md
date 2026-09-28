# 路床移交接口及界面契约

本契约已于2026-09-24实施；测试与当前项目验证结果见[验证指南](../quickstart.md)。

## 主数据字段与保存

字段和兼容规则见[数据模型](../data-model.md)。沿用主数据detail、workpoint及Excel接口；Excel追加三态与说明参数列，日期列保留，缺新列的旧模板仍可导入。

新增`PUT /api/project-master/versions/{version_id}/pavement-sections/{section_id}/handover`：

```json
{
  "status": "handed_over",
  "available_date": null,
  "note": "用户确认路床已移交",
  "created_by": "本地计划工程师"
}
```

成功200返回`ProjectMasterVersionDetail`；内容相同复用原版本。404表示段/版本不存在，409 `CURRENT_VERSION_CHANGED`表示并发基线失效，422表示状态、日期或所属领域不合法。失败不创建已确认新版本，不清空输入。

只更改目标段三个移交参数，保留结构层与其他段。沿用现有确认和版本引用保护；前端保存成功刷新版本并触发既有派生数据失效。

## 任务生成与求解

既有`POST /api/generate-schedule-input`和`POST /api/solve-scenario`继续从确认主数据materialize，不能以客户端备注覆盖段状态。

新增可选`ScheduleInput.pavement_handover_scope`，结构见[数据模型](../data-model.md)。生成响应同时将该对象写入`source_summary.pavement_handover`，求解结果（含失败与全部待定）写入`stats.pavement_handover`。桥梁省略，旧路面无该字段仍可读取。

- 混合范围：生成纳入段任务，待定列表保持可见；非阻断说明使用`PAVEMENT_ROADBED_PENDING`。
- 全部待定：不调用求解器，返回现有`MODEL_INVALID`与`PAVEMENT_NO_SCHEDULABLE_SECTION`；页面专门显示“暂无可开工施工段”。不得显示“全项目0天完成”。
- 指定日期缺失、非法状态/日期：`PAVEMENT_ROADBED_INVALID`，定位段/任务，阻止求解。
- 直接`POST /api/solve`含pending任务：`PAVEMENT_ROADBED_NOT_AVAILABLE`。dated/handed_over按同一规则检查和施加硬边界，不因缺失客户端execution_constraint而跳过。
- 未知引用、非法工效、无机组、未确认养生等继续使用原有错误。范围元数据不得把其他失败隐藏为已完成。
- Demo镜像继续明确拒绝路面请求，不能静默回退到桥梁；本次不实现第二套路面求解器。

## 界面

主数据：既有施工段下维护状态、日期及说明，仅“指定日期”显示必填日期。列表分别显示日期、“已移交”或“移交待定”及原因。保留当前四个结构层编辑和紧凑布局。

任务：纳入段显示实际工效及工序；待定段可保留主数据/配置查看，但明确“未排程”，不填预计开始/结束日期。

结果：显示“纳入21段／待定4段”等真实范围与清单；有排除项时完成日期标为本次纳入范围。旧历史结果不补写当前范围。

加载、错误、空态：加载沿用现有状态；失败保留草稿；并发冲突提示重新读取；全待定与无主数据分开呈现。切换状态/日期并保存后旧任务和结果失效，手动重新生成/求解使用新状态。
