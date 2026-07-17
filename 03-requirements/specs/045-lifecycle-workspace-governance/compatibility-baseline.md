# 045 迁移前兼容基线

本基线冻结 T003 时仍需保持可用的根入口和路径契约。后续目录迁移可以更新路径，但不得改变公开行为、依赖锁、固定样例语义或平台入口能力。

## 根 npm 工作区

- 根包：`bridge-cpsat-scheduler`，`private: true`
- 当前 workspace：`frontend`
- 统一命令：`build`、`frontend:dev`、`frontend:preview`、`typecheck`、`test`、`verify:build-budget`、`verify:architecture`、`verify`
- `package.json` SHA-256：`31e0ae372a9b95bfc81ec701a939781c1448f052e22873fd2ecdfa253b175820`
- `package-lock.json` SHA-256：`9aca184df5408b44894ecee878a065edf6622a63d340aee493ea6e823160d45c`

## 后端入口

- 模块入口：`backend/app/main.py`，公开 ASGI 对象为 `app.main:app`
- 本地命令：`python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`
- 健康检查：`GET /api/health`
- `backend/app/main.py` SHA-256：`e7354a641d34d03a22ab10d165e4d8127224f515663740a0d02bf70bd9f57d04`
- `requirements.txt` SHA-256：`e18da0ba242f3713b8a04b16f6b8285bea70416e88f9323187f0ac2c098098a0`

## 前端入口

- 包：`frontend/package.json`
- 开发入口：`vite --host 127.0.0.1`
- 构建入口：`tsc && vite build`
- 测试入口：`node --test tests/*.test.mjs`
- `frontend/package.json` SHA-256：`afa9e973d76b726970eb81d39a8598338a014de5131f6ebd4f9d2b926b232361`

## Docker 与 Netlify

- Docker 构建上下文为仓库根，复制 `requirements.txt`、`backend/`、`examples/`，启动 `uvicorn ... --app-dir backend`。
- `Dockerfile` SHA-256：`c3b80cc2cea6caabef14e30251bde9ec1bae30e032bf79072e18b97048c7494f`
- Netlify 构建命令：`npm run build`
- Netlify 发布目录：`frontend/dist`
- `netlify.toml` SHA-256：`d10fdc88d012f38092bab6debd3d53b3560957ebe9f7ec1bd51419fe1d51867c`

## Spec Kit 入口

- 根发现目录：`.specify/`
- 当前活动指针：`specs/045-lifecycle-workspace-governance`
- prerequisite：`.specify/scripts/powershell/check-prerequisites.ps1`
- 当前 `feature.json` SHA-256：`2ee9a3566f024e13a4f8132000c1a096348dc09252fe136f14de21ba07eb2450`
- 当前 `common.ps1` SHA-256：`1d64eef3a96d92ade478af5cdc8494791fd62f70961ce0187ea2e057a2aa2b65`
- T015 只增加 `specs/` 与 `03-requirements/specs/` 双路径解析；默认创建位置直到 T067 才切换。

## Skill 发现入口

根 `.agents/skills/` 当前可发现 11 个项目 Skill：

```text
demo-algorithm-explainer
speckit-analyze
speckit-checklist
speckit-clarify
speckit-constitution
speckit-converge
speckit-implement
speckit-plan
speckit-specify
speckit-tasks
speckit-taskstoissues
```

通用 `speckit-*` Skill 在本次迁移后仍保留根发现入口；Demo 算法 Skill 的权威内容迁移要等 T069。

## 兼容性验收边界

1. 迁移前后根命令能力集合一致。
2. API、共享契约、固定样例结果和正式二进制无未批准变化。
3. 旧规格指针在物理迁移后能够解析到新目录；T067 前不改变默认创建目录。
4. 迁移批次未批准时，以上文件和入口只允许增加兼容分支，不允许提前切换目标路径。

