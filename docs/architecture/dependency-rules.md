# 依赖与公开入口规则

## 后端方向

```text
api/routers -> application/services -> domain/solver -> contracts
bootstrap   -> api/routers + config
compatibility façades -> new owning module
```

- `contracts/` 只依赖标准库、Pydantic 和同包低层契约；禁止依赖 API、service、solver 或存储。
- `scheduling/` 禁止依赖 `app.main` 和 HTTP router。
- router 只做请求/响应装配和统一异常映射，不实现求解、文件解析或仓储规则。
- 架梁、计划管控和助手通过 application façade 组合，不直接穿透其他领域内部文件。
- `app.models`、`app.scenario`、`app.solver`、旧 `services/*` 在迁移期只向新所有权转发；同一业务只能有一个实现。

## 前端方向

```text
app -> features -> domain/contracts
app -> api -> contracts
shared components -> contracts (必要时)
```

- `contracts/` 不依赖 React、API 或 feature。
- `domain/` 保持纯函数，不调用网络、不读取组件状态。
- feature 不直接导入另一 feature 的内部文件；跨 feature 组合由 app adapter/controller 完成，或只导入对方公开 `index.ts`。
- API 层不拥有页面状态；workspace controller 不实现领域计算。
- `types/scheduler.ts`、`api/schedulerApi.ts` 是兼容出口，不新增业务实现。
- feature CSS 归对应 feature；全局 `styles.css` 只负责稳定导入顺序。

## 自动门禁

```powershell
npm.cmd run verify:architecture
npm.cmd run verify
```

`verify:architecture` 比较公开契约并检查依赖、仓库和文档；`verify` 还编排类型、全量测试、构建和 5% 包体门禁。

## 禁止事项

- 不从 contracts/domain 反向依赖 UI、HTTP、存储或运行时装配。
- 不为避免迁移而复制业务算法形成两份实现。
- 不绕过 façade 从新模块导入旧模块内部私有函数，除非有迁移任务和测试保护。
- 不在纯重构中新增/升级依赖、改变锁文件、接口字段、状态码、目标函数或存储路径。
