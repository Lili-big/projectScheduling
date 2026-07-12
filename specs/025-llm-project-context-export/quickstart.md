# 快速验证：三方案生成前 LLM 项目信息下载

## 前置条件

- 后端和前端依赖已安装。
- 使用默认项目场景即可验证本地回退；外部 LLM 成功与失败回退可通过现有测试替身验证，不需要在文档中配置真实密钥。

## 自动验证

```powershell
python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q
```

预期：上下文同源、六分区、安全字段排除和回退场景测试通过。

```powershell
cd frontend
npm.cmd run build
```

预期：TypeScript 类型检查和 Vite 生产构建通过。

## 页面验证

1. 启动本地后端和前端，进入“AI 多方案比选”。
2. 点击“生成三方案”。
3. 确认成功后出现“下载本次 LLM 项目信息 JSON”。
4. 下载并解析文件，确认顶层只有六个约定分区，中文可读。
5. 对比页面工程画像、当前资源池和下载内容，确认值一致。
6. 再次生成，确认链接对应最新上下文。
7. 修改项目场景，确认旧链接消失。

## 回退验证

1. 使用本地 Provider 生成三方案，确认下载入口仍出现。
2. 使用测试替身模拟外部 LLM 调用失败并回退，确认响应成功且可下载上下文。
3. 模拟初始化接口整体失败，确认页面显示错误且不沿用旧下载入口。

## 安全检查

在下载 JSON 中搜索以下词项，预期均不出现配置值：

- `API_KEY`
- `Authorization`
- `Endpoint`
- `model`
- `system`
- `output_schema`
