# NavoWork

使用 **npm workspaces** 管理的 monorepo。前端应用集中在 [`fontend/`](./fontend/)，根目录负责依赖锁定、工作区命令和共享代码格式。

```text
NavoWork/
├── package.json          # workspace 定义与统一命令
├── package-lock.json     # 全仓库唯一锁文件
├── .prettierrc.json       # 共享格式规范
├── LICENSE
└── fontend/              # @navowork/fontend · Navowork 前端
    ├── package.json      # 前端依赖与脚本
    ├── .env.example      # 环境配置示例
    ├── src/              # 页面、组件、API 与 Mock
    ├── public/
    ├── tests/            # Playwright 浏览器测试
    ├── docs/             # 联调、验证、截图
    ├── vite.config.ts
    ├── vitest.config.ts
    ├── playwright.config.ts
    └── tsconfig.json
```

## 启动

推荐 Node.js 22.12+ 或 24。在仓库根目录执行：

```sh
npm ci
npm run dev
```

打开 [Navowork 本地预览](http://127.0.0.1:5173/)。默认 Mock 演示模式，业务数据为合成测试数据；真实服务尚待联调。开发服务器固定使用 5173，端口占用时直接报告错误。

## 根目录命令

| 命令                   | 行为                                                        |
| ---------------------- | ----------------------------------------------------------- |
| `npm run dev`          | 启动 `fontend` 开发服务器                                   |
| `npm run build`        | 构建所有提供 build 脚本的工作区；当前产物为 `fontend/dist/` |
| `npm run preview`      | 预览前端生产构建                                            |
| `npm run typecheck`    | 检查工作区 TypeScript                                       |
| `npm test`             | 执行工作区单元/接口测试                                     |
| `npm run test:e2e`     | 执行前端浏览器测试                                          |
| `npm run format`       | 格式化整个仓库                                              |
| `npm run format:check` | 检查整个仓库格式                                            |

首次运行浏览器测试需安装 Chromium：

```sh
npm exec --workspace=fontend -- playwright install chromium
```

按文件运行浏览器测试：

```sh
npm run test:e2e -- tests/e2e/resources.spec.ts
```

也可显式指定工作区：`npm run dev --workspace=fontend`，或进入 `fontend/` 执行包内命令。新增前端依赖从根目录执行 `npm install <包名> --workspace=fontend`；共享工具用根目录 devDependencies。`node_modules/` 可由 npm 提升至根目录，这是 workspace 的正常布局。

## 配置与文档

- 环境文件放在 **`fontend/.env.local`**，参考 [`fontend/.env.example`](./fontend/.env.example)。
- 前端说明与功能边界：[`fontend/README.md`](./fontend/README.md)。
- 品牌图标、双主题与颜色变量：[`fontend/docs/BRAND_THEME.md`](./fontend/docs/BRAND_THEME.md)。
- 接口联调：[`fontend/docs/INTEGRATION.md`](./fontend/docs/INTEGRATION.md)。
- 验证记录：[`fontend/docs/VALIDATION.md`](./fontend/docs/VALIDATION.md)。
- 开源依赖：[`fontend/THIRD_PARTY.md`](./fontend/THIRD_PARTY.md)。
- 产品需求：[`doc/TradeWorkbench_PRD_v1.0.md`](./doc/TradeWorkbench_PRD_v1.0.md)。
- 后端开发计划：[`后端开发计划.md`](./后端开发计划.md)。
- 后端详细设计与前端接口映射：[`doc/TradeWorkbench_Backend_Design_v1.0.md`](./doc/TradeWorkbench_Backend_Design_v1.0.md)。
- Agent 节点图与阶段门禁：[`doc/TradeWorkbench_Agent_Node_Graph_v1.0.md`](./doc/TradeWorkbench_Agent_Node_Graph_v1.0.md)。

**业务主线：** 客户开发与询盘评估 → 需求书面确认 → 供应商核价/报价与打样 → PO/合同及付款保障核验 → 生产与验货 → 出口出运 → 收款与售后。首轮演示实现前半段及生产资料准备；通用变更机制分析任意业务变化对事实、成果、SOP 节点和门禁的影响，并引导用户逐项维护。Agent 节点和阶段门禁见后端详细设计第 12.7 节。

**核心技术栈：** 已有前端为 React 19 + TypeScript + Vite 7；规划后端为 Python + FastAPI + Pydantic + SQLAlchemy/Alembic + SQLite（WAL）+ 单个独立 Worker。Agent 规划使用 LangGraph 主图与持久化检查点，按需接入 LangChain 中间件处理上下文与调用限额；结构化工具负责业务操作，核价和审批由确定性代码处理。后端是独立 Python 项目，不加入 npm workspaces。

后续新增 JavaScript 共享包时，再在根 `package.json` 的 `workspaces` 中增加实际目录；当前 npm workspace 仅包含前端。
