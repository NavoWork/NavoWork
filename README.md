# NavoWork

包袋出口业务工作台。前端为 React/Vite，后端为 FastAPI + SQLAlchemy/SQLite，任务由独立 LangGraph Worker 处理。当前主链路：新询盘 → 客户与询盘评估 → 箱包 Tech Pack/BOM → 多供应商核价与客户报价 → 打样 → PO/PI 与付款保障 → 生产资料与验货放行。Agent 通过受控工具读写节点成果，并检索知识库和公司资产；批准、付款核验和放行由人执行。

## 本地启动（Windows）

需要 Python 3.12+ 和 Node.js 20+。在仓库根目录执行：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e agent-kit -e 'backend[test]'
npm ci
Copy-Item backend/.env.example backend/.env
python dev.py
```

浏览器打开 <http://127.0.0.1:5173>。演示账号为 `demo@navowork.local`，密码为 `ChangeMe123!`；可在 `backend/.env` 修改。`dev.py` 自动运行迁移、启动 API、Worker 和 real 模式前端，按 Ctrl+C 关闭。数据写在 `backend/data/`，上传原件写在 `backend/storage/`，均不纳入 Git。

新询盘从侧栏“新建工作”创建；进入 Cases 后使用三栏工作台：左侧业务节点、中间成果与结构化编辑、右侧 Agent 对话。对话中的工具调用会读取项目原件、知识库和公司资产，并把结果写入对应成果版本。

## 比赛演示资料

新的演示包只导入客户原件、知识库和公司资产；**不预生成需求、报价、样品、订单或生产资料**。打开 Cases 后由你指挥 Agent 逐节点推进。

```powershell
backend/.venv/Scripts/python.exe demo/seed.py
```

会创建三条待办：

- `inq_demo_de`：Nordlicht Outdoor 定制通勤背包，含客户询盘、两家工厂报价、包装变更、PO、样品反馈、客户确认、内部批准、付款凭据和供应商确认原件。
- `inq_demo_mx`：Casa Verde 帆布袋试单，演示 300 件与 MOQ 500 的澄清。
- `inq_demo_uk`：信息不足的英国促销询盘，演示先澄清再推进。

演示路径：`询盘评估 → Tech Pack/BOM → 供应商报价与核价 → 客户报价 → 打样 → PO/PI 与付款 → 生产资料与放行`。每个节点由 Agent 通过工具读取原件、写成果或向用户提问；人工确认、付款核验和放行由界面单独记录。

知识库包含 8 篇业务规则（客户评估、箱包 Tech Pack、核价、贸易术语、打样、订单/PI、生产/验货、材料参考）；Agent 会按节点加载对应 Skill。模型配置：

```dotenv
MODEL_API_KEY=...
MODEL_NAME=gpt-6.1-sol
MODEL_BASE_URL=https://api.tokenhubcloud.net/v1
```

未配置模型时，Agent 工具不会伪造执行结果，会明确返回 `MODEL_NOT_CONFIGURED`。

## 验证

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests agent-kit/tests -q
npm run typecheck
npm run test
npm run build
```

可在 `backend/.env` 设置 `MODEL_API_KEY`、`MODEL_NAME` 和 `MODEL_BASE_URL` 启用 Agent 工具调用；未配置时不会伪造执行结果。正式商业批准、外部确认、付款核验和生产放行由服务端门禁控制，草稿下载不表示已发送或已开工。演示账号和默认密钥仅用于本机演示，不可公开部署。

## 开发与文档

根目录 npm workspaces 只包含 `fontend/`。直接执行 `npm run dev` 时，前端连接 `http://127.0.0.1:8000` 的 API；使用 `python dev.py` 可同时启动全部服务。前后端浏览器回归在 `fontend/` 执行 `npm run test:e2e`（会启动独立临时数据库）；Windows 默认使用已安装的 Edge，可用 `PLAYWRIGHT_BROWSER_PATH` 指定 Chrome/Edge 路径。

- [Workbench v2 契约：阶段、成果、工具与 Skill](doc/18-workbench-v2-contract.md)
- [产品需求](doc/TradeWorkbench_PRD_v1.0.md)
- [后端设计](doc/TradeWorkbench_Backend_Design_v1.0.md)
- [Agent 节点图](doc/TradeWorkbench_Agent_Node_Graph_v1.0.md)
- [前端接口说明](fontend/docs/INTEGRATION.md)
- [独立评测入口](evaluation/README.md)
