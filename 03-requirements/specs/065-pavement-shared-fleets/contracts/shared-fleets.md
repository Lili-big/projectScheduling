# 契约：路面共享机组

## API与持久化

- GET /api/demo-scenario?engineering_domain=pavement&project_id=pavement-project：返回工艺多选能力，旧专用池缺失/空列表规范化为原类型当前工艺ID。
- PUT /api/local-scenario-config：沿用整体请求及project_id/version校验；有效组非空能力、已知工艺ID、唯一池ID、非负整数数量、非空名称；保存失败422或现有存储错误503，不覆盖成功配置。
- 生成及场景求解入口：同一池只展开quantity个实例， Resource.compatible_process_ids与Task.pavement_context.process_id必须传递。
- POST /api/solve：不依赖前端选择，按同样能力、范围、施工互斥、转场硬约束验证/求解。
- 演示镜像继续422 PAVEMENT_FEATURE_NOT_SUPPORTED，不宣称其支持该功能。

示例（既有池局部字段，不是完整保存请求）：

```json
{
  "id": "pavement-cement_stabilized_base-pool",
  "type": "water_stable_paving_crew",
  "label": "碎石/水稳共享机组",
  "quantity": 1,
  "max_quantity": 1,
  "transfer_days": 1,
  "compatible_process_ids": ["pavement-granular_base", "pavement-cement_stabilized_base"]
}
```

保留现有Task.compatible_resource_types作为旧类别字段；路面新能力匹配使用精确工艺ID。新资源字段和任务字段均为可选、缺省省略，不改变桥梁请求/响应。

## 算法合同

输入单位：数量为套、工期及转场为自然日、工效继续使用原单位/天。

候选实例必须同时满足：启用、来源数量实际展开、工点授权、任务工艺在实例compatible_process_ids内。新能力存在而任务缺process_id时不得模糊匹配。旧资源无能力字段只回退其原单一专用类型；通用类型禁止回退。

每个施工任务恰选一套候选实例。同一实例所有工艺的施工区间NoOverlap；养生等待不占用实例。同段同幅无转场，不同位置的相邻任务必须满足next.start >= previous.end + transfer_days。换工艺本身不加时间，也不重置路径。

不变：工期取现有工效规则；多套不缩短单任务工期；全部工序及日期约束保留；目标仍最早整体可用，无新增软约束。结果沿用assigned_resource_id/resource_allocations和pavement_summary.transfers，名称采用实际池/实例名称。

## 诊断、空态和兼容

| 情况 | 行为 |
| --- | --- |
| 有效任务没有候选实例 | MODEL_INVALID；PAVEMENT_RESOURCE_MISSING，指向具体任务及工艺 |
| 能力未知、重复池ID、显式空能力实例、通用池缺能力、旧任务无法匹配新能力 | MODEL_INVALID及PAVEMENT_REFERENCE_INVALID；保存配置阶段以422拒绝对应输入 |
| 有效实例转场未填 | PAVEMENT_TRANSFER_UNCONFIRMED；不默认0 |
| 0套或停用且转场null | 不展开、不阻断其他有效资源；界面显示无可用机组/停用 |
| 合法模型因资源/工序/期限冲突不可行 | 沿用INFEASIBLE，不自动增配或放松规则 |
| 旧专用池缺失/空列表 | 加载及旧生成入口仅恢复本类工艺；新保存有效组清空则拒绝 |
| 未配置任何机组 | 资源页显示空态及新增入口；核心任务无资源时明确阻止求解 |
| 保存中/保存失败 | 保存中禁止重复提交及编辑；失败保留编辑并显示错误 |

过程库删除被引用工艺不能静默放宽为任意工艺；既有脏输入继续诊断。不得通过此变更补写064路床状态或养生天数。
