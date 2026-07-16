# Demo API 参考镜像

`api.mts` 只保留旧 Netlify Demo API 的参考实现，用于历史字段和降级行为核对。

当前正式链路是 Netlify 静态前端连接独立 FastAPI/OR-Tools 后端。`netlify.toml` 没有 Functions 目录配置，本目录不会参与部署，也不能替代完整的 45 路由后端。

验证：

```powershell
node .\tools\demo-api-mirror\verify.mjs
```

该命令执行 TypeScript `noEmit` 检查，并确认 `netlify.toml` 没有把参考镜像配置成部署函数。除非通过独立规格明确恢复 Netlify API，否则不要把文件移回 `netlify/functions/`。
