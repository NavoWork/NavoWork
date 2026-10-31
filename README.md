# NavoWork

包袋出口业务工作台。前端为 React/Vite，后端为 FastAPI + SQLAlchemy/SQLite，任务由独立 LangGraph Worker 处理。当前可运行的核心流程：询盘建档、证据和候选事实、规格与询价/核价/报价草稿、成果版本和导出、任意业务变更的节点影响与候选修订、样品/订单/付款保障记录和生产资料门禁。生产进度、真实物流和银行数据仍需外部资料接入。

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

## 比赛演示

```powershell
backend/.venv/Scripts/python.exe demo/seed.py
python dev.py
```

默认导入 `intake` 批次的德国定制背包、墨西哥帆布袋、英国品牌礼品三条新询盘。每条只有客户原文和询盘原件，初始没有规格、供应商报价记录、报价、样品、订单或批准。重复导入保留已做的工作；需要重新演示时使用 `demo/seed.py --batch rehearsal2`。

导入同时准备 8 篇业务知识和 47 份公司资产，其中包含 `test/core15` 的 17 份业务文件和 9 封原件。后续报价、样品与订单材料只在资产库中，用户进入对应环节时指挥 Agent 选择引用。core15 是 WB-26 / V3 / S03 档案，引用前应核对款号与版本，不能直接当作 BP-DE-3000 的当前确认。

打开“德国定制背包询盘”，先发送“请整理客户需求和待确认事项”。之后依次要求生成规格、读取工厂报价并核价、准备客户报价。每次只推进本轮指定环节；后续节点保持未开始。聊天会显示工具执行情况，保存的需求、业务草稿和知识/资产引用会同步回工作台。

详细指令见 [演示操作手册](demo/competition_v1/演示操作手册.md)。`demo/advance.py` 仅保留为手动辅助入口，默认指向 `intake`；比赛主线直接在对话中完成。

在 `backend/.env` 中设置 `MODEL_BASE_URL`、`MODEL_API_KEY`、`MODEL_NAME`，即可启用模型工具调用。模型凭据只放本机配置，不提交到仓库。工作空间设置管理默认贸易条款、核价参数与启用的业务技能；最终报价仍使用本轮明确选择的供应商与条件。

## 验证

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests agent-kit/tests -q
npm run typecheck
npm run test
npm run build
```

可在 `backend/.env` 设置 `MODEL_API_KEY` 和 `MODEL_NAME` 启用模型抽取；未配置时用有限规则提取，未知字段保持待确认。正式商业批准、外部确认和生产放行由服务端门禁控制，草稿下载不表示已发送或已开工。演示账号和默认密钥仅用于本机演示，不可公开部署。

新增文件工具执行链见 [agent-kit/README.md](agent-kit/README.md)。设置 `AGENT_FILE_TOOLS=1` 后，对话报价/变更目标使用真实模型工具调用，读取已上传的 Case 资料及本次显式引用的画板附件，返回真实规格 DOCX、成本 XLSX、客户报价 XLSX/PDF。汇率和毛利可在对话中明确提供，例如“汇率7.20，毛利20%”。缺价先生成草稿，再通过现有澄清机制补证继续。此模式无模型配置时明确失败；确定性离线回放不代表真实 Agent 或浏览器集成已验收。

文件工具无模型场景的真实浏览器检查：在 `fontend/` 执行 `npm run test:e2e -- --config=playwright.file-tools.config.ts`。该检查会使用独立临时业务存储、上传实际 XLSX，并验证 API/Worker/页面明确失败及刷新后的文件保存；它不替代真实模型报价主线。

## 开发与文档

根目录 npm workspaces 只包含 `fontend/`。直接执行 `npm run dev` 时，前端会连接 `http://127.0.0.1:8000` 的 API；使用 `python dev.py` 可同时启动全部服务。需要体验原有纯前端合成数据模式时，在 `fontend/.env.local` 写入 `VITE_API_MODE=mock`，再启动前端。单独运行现有 Mock 浏览器回归用 `npm run test:e2e`；真实前后端浏览器联调用 `npm run test:e2e -- --config=playwright.real.config.ts`（在 `fontend/` 目录）。Windows 测试默认使用已安装的 Edge，可用 `PLAYWRIGHT_BROWSER_PATH` 指定其他浏览器。

- [产品需求](doc/Navowork_PRD_v1.0_满血版.md)
- [后端设计](doc/TradeWorkbench_Backend_Design_v1.0.md)
- [Agent 节点图](doc/TradeWorkbench_Agent_Node_Graph_v1.0.md)
- [新版前端适配：架构、实际节点链路与接口 v1.1](doc/Frontend_Backend_Adaptation_v1.1.md)
- [后端开发计划](后端开发计划.md)
- [前端接口说明](fontend/docs/INTEGRATION.md)
- [文件 Agent 验证记录](agent-kit/docs/verification.md)
- [BOM 图片候选模块](extensions/bom-vision/README.md)
- [样品与订单 Skills](extensions/order-skills/README.md)
- [独立评测入口](evaluation/README.md)
