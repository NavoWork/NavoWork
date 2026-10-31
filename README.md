# NavoWork

包袋出口业务工作台。前端为 React/Vite，后端为 FastAPI + SQLAlchemy/SQLite，任务由独立 LangGraph Worker 处理。当前可运行的核心流程：询盘建档、证据和候选事实、规格与询价/核价/报价草稿、成果版本和导出、任意业务变更的节点影响与候选修订、样品/订单/付款保障记录和生产资料门禁。生产进度、真实物流和银行数据仍需外部资料接入。

## 本地启动（Windows）

需要 Python 3.12+ 和 Node.js 20+。在仓库根目录执行：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e 'backend[test]'
npm ci
Copy-Item backend/.env.example backend/.env
python dev.py
```

浏览器打开 <http://127.0.0.1:5173>。演示账号为 `demo@navowork.local`，密码为 `ChangeMe123!`；可在 `backend/.env` 修改。`dev.py` 自动运行迁移、启动 API、Worker 和 real 模式前端，按 Ctrl+C 关闭。数据写在 `backend/data/`，上传原件写在 `backend/storage/`，均不纳入 Git。

## 验证

```powershell
backend/.venv/Scripts/python.exe -m pytest -q
npm run typecheck
npm run test
npm run build
```

可在 `backend/.env` 设置 `MODEL_API_KEY` 和 `MODEL_NAME` 启用模型抽取；未配置时用有限规则提取，未知字段保持待确认。正式商业批准、外部确认和生产放行由服务端门禁控制，草稿下载不表示已发送或已开工。演示账号和默认密钥仅用于本机演示，不可公开部署。

## 开发与文档

根目录 npm workspaces 只包含 `fontend/`。直接执行 `npm run dev` 时，前端会连接 `http://127.0.0.1:8000` 的 API；使用 `python dev.py` 可同时启动全部服务。需要体验原有纯前端合成数据模式时，在 `fontend/.env.local` 写入 `VITE_API_MODE=mock`，再启动前端。单独运行现有 Mock 浏览器回归用 `npm run test:e2e`；真实前后端浏览器联调用 `npm run test:e2e -- --config=playwright.real.config.ts`（在 `fontend/` 目录）。Windows 测试默认使用已安装的 Edge，可用 `PLAYWRIGHT_BROWSER_PATH` 指定其他浏览器。

- [产品需求](doc/TradeWorkbench_PRD_v1.0.md)
- [后端设计](doc/TradeWorkbench_Backend_Design_v1.0.md)
- [Agent 节点图](doc/TradeWorkbench_Agent_Node_Graph_v1.0.md)
- [后端开发计划](后端开发计划.md)
- [前端接口说明](fontend/docs/INTEGRATION.md)
