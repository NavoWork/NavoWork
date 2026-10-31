# EasyWork · 出海外贸工作台

按任务包 A 与 EasyWork V1.0 契约搭建的独立前端工程。默认是明确标注的 **Mock 模式**，用于体验、前端回归及等待 B/C/D 服务时并行开发。真实认证、模型理解、报价、规则校验和服务端持久化尚需后端联调。

## 本地启动

推荐 Node.js 22.12+ 或 24，npm 11。本次环境使用 Node.js 24.15.0。

```sh
cd /Users/mac/Desktop/Navo/NavoWork
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 ，填写称呼进入演示工作空间。演示称呼不是真实认证。四条合成询盘覆盖待办、进行中、待确认、已结束。墨西哥帆布袋示例可演示 300/600 件方案、900 件超库存失败、双语回复、草稿冲突与版本对比。新录入原文保留原样，Mock 不会假装有模型能力：返回明确的需补信息结果。

## 使用的开源组件

- React / TypeScript / Vite：界面、类型与构建。
- React Router：页面 URL 与深链接。
- TanStack Query：服务端状态、分页、缓存与请求取消。
- React Flow（`@xyflow/react`，MIT）：询盘无限画板、自定义资料预览节点、拖拽缩放、连线与小地图。
- Radix Dialog：弹窗焦点约束、键盘与屏幕阅读器语义。
- Lucide React：图标。
- idb：IndexedDB 的 Promise API；只为模拟服务持久化测试数据。
- Papa Parse：CSV 解析，业务校验仍由资源接口返回。
- Vitest / fake-indexeddb / Playwright：适配器与浏览器回归。

本包属于 npm workspace `@navowork/fontend`，源码、测试、配置和文档均位于 `fontend/`。依赖安装与共享格式化从仓库根目录执行；Vite 环境文件在本包目录读取。锁定安装版本见根目录 `package-lock.json`。许可证见 [THIRD_PARTY.md](./THIRD_PARTY.md)。

## 已接出的前端入口

| 页面      | 路径             | 主要行为                                              |
| --------- | ---------------- | ----------------------------------------------------- |
| 工作台    | `/`              | 四状态计数、筛选搜索、分页、新建                      |
| 询盘      | `/inquiries/:id` | 独立 Tab、三阶段、四结果、Run、草稿、来源、历史、导出 |
| 知识 Wiki | `/knowledge`     | 知识草稿/发布与商品 CSV 导入                          |
| 资产库    | `/assets`        | 文件上传、元信息、预览与下载                          |
| 能力目录  | `/capabilities`  | 必需/可选能力及管理员启停                             |

关闭 Tab 不删除询盘。阶段按钮只导航。后台 Run 归属于询盘，允许切换其他询盘。未发送文字与视图偏好以 user/workspace/inquiry 为键暂存。正式业务数据经 API 读写，不能把本地演示存储当作生产数据库。

询盘左侧提供文件夹目录、无限画板和资料标签页；AI 对话、运行进度及输入框放在右侧，右侧可切换查看业务结果。画板节点只预览，双击或在目录中按 Enter 打开标签页；原始询盘、沟通记录、需求规格、风险、方案报价、双语回复、固定来源、附件、笔记及版本记录使用各自的页面。首次处理前的原文通过询盘 PATCH 保存，回复沿用版本草稿接口与冲突处理。需求、风险及报价的人工修改先保存为本机工作草稿，可交给助手核对并生成新业务版本。画板布局、打开的标签、笔记、文件夹和附件显示名按用户、空间及询盘隔离保存于浏览器；本机导入文件存于 IndexedDB。尚未接入团队云端同步。详细行为见 [docs/INQUIRY_CANVAS.md](./docs/INQUIRY_CANVAS.md)。

工作空间设置内可触发网络失败、会话过期、无权限、草稿冲突与运行失败；持续故障可选“正常请求”恢复。会话过期重新登录后恢复。

## 真实接口配置

在 `fontend/` 内复制 `.env.example` 为 `.env.local`：

```dotenv
VITE_API_MODE=real
VITE_API_BASE_URL=/api/v1
API_PROXY_TARGET=http://127.0.0.1:8000
```

重新启动开发服务器。接口使用 Cookie credentials，并遵守 `/api/v1/workspaces/{workspaceId}` 契约。真实模式失败不会回退到 Mock。认证响应、资源列表和错误包的前端适配约定见 [docs/INTEGRATION.md](./docs/INTEGRATION.md)。不得在 `VITE_` 环境变量中放模型密钥或服务端凭证。

部署构建：`npm run build` 输出 `fontend/dist/`（相对仓库根目录）。Web 服务器需要将前端深链接回退到 `index.html`，并将 `/api` 指向后端；开发期 Vite proxy 不包含在静态构建中。

## 验证

```sh
npm run typecheck
npm test
npm exec --workspace=fontend -- playwright install chromium
npm run test:e2e
npm run build
```

本次验证结果和限制见 [docs/VALIDATION.md](./docs/VALIDATION.md)。浏览器截图保存在 `docs/screenshots/`。测试演示数据与真实 V1 验收分开记录。
