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

后续加入后端或共享包时，在根 `package.json` 的 `workspaces` 中增加实际目录；本次仅迁移已有前端。
