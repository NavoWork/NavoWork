# NavoWork

包袋出口业务工作台。前端为 React/Vite，后端为 FastAPI + SQLAlchemy/SQLite，任务由独立 LangGraph Worker 处理。当前主链路：新询盘 → 客户与询盘评估 → 箱包 Tech Pack/BOM → 多供应商核价与客户报价 → 打样 → PO/PI 与付款保障 → 生产资料与验货放行。Agent 通过受控工具读写节点成果，并检索知识库和公司资产；批准、付款核验和放行由人执行。

## 本地启动（Linux / macOS / Windows）

需要 Python 3.12+ 和 Node.js 20+。在仓库根目录选择对应入口；首次启动会自动创建 `backend/.venv`、安装 Python/npm 依赖，并从 `backend/.env.example` 生成 `backend/.env`：

| 系统 | 启动方式 |
| --- | --- |
| Linux / macOS | `./start.sh` |
| macOS Finder | 双击 `start.command` |
| Windows PowerShell | `.\start.ps1` |
| Windows CMD / 双击 | 双击 `start.bat`，或在 CMD 中执行 `start.bat` |

PowerShell 若提示禁止运行脚本，可执行 `powershell -ExecutionPolicy Bypass -File .\start.ps1`，或直接双击 `start.bat`。

脚本会先执行数据库迁移，再启动 API（8000）、LangGraph Worker 和前端（5173）；按 Ctrl+C 停止全部服务。依赖已就绪时启动只需几秒。常用参数：`--setup-only` 只准备环境、`--no-install` 跳过自动安装、`--skip-migrate` 跳过迁移；`./start.sh --help` 可查看说明。`python dev.py` 与这些脚本等价。

浏览器打开 <http://127.0.0.1:5173>。演示账号为 `demo@navowork.local`，密码为 `ChangeMe123!`；可在 `backend/.env` 修改。数据写在 `backend/data/`，上传原件写在 `backend/storage/`，均不纳入 Git。

手动安装（可选；自动安装不可用或 CI 环境）：

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e agent-kit -e 'backend[test]'
npm ci
cp backend/.env.example backend/.env
backend/.venv/bin/python dev.py
```

Windows 手动安装时把 `backend/.venv/bin/python` 换成 `backend\.venv\Scripts\python.exe`，`cp` 换成 `Copy-Item`。后文示例沿用 Windows 路径；Linux/macOS 请将 `backend/.venv/Scripts/python.exe` 换成 `backend/.venv/bin/python`。若从 ZIP 解压后提示脚本没有执行权限，先运行 `chmod +x start.sh start.command`。

新询盘从侧栏“新建工作”创建；进入 Cases 后使用三栏工作台：左侧业务节点、中间成果与结构化编辑、右侧 Agent 对话。对话中的工具调用会读取项目原件、知识库和公司资产，并把结果写入对应成果版本。

## 文件、研究与自动同步

工作台保留 guilimao 的业务 Agent 工具链，同时组合受控 `file_` 工具读取、复制、编辑、校验和下载真实文件。成果区支持 DOCX 段落/表格/图片与简单 XLSX 单元格/公式的内联编辑和内容预览。人工文件版本会进入同一 Agent 的可读文件列表，原件和历史版本不覆盖。

系统导出的规格 DOCX/XLSX、BOM XLSX 带显式字段映射。保存数量或 BOM 用量/价格/损耗后，自动重算绑定的成本、报价和订单差异，刷新相关原生导出；同组记录快照、一致性标识及失败格式，允许只重试失败分支。未知映射、旧基线和制造适用性进入待复核，不猜测价格或继承审批。

需求节点的“竞品、概念图与 BOM 识别”支持有来源的比较、设计建议采纳、规格绑定的真实图像服务接口和图片 BOM 候选复核。图像/VLM 服务需要单独配置并验收，参见 [本轮 PRD 验收与边界](doc/19-guilimao-prd-acceptance.md) 和 [真实服务验收](backend/tests/live/README.md)。Office PDF 是同文件版本的基础内容预览，不承诺 Office 分页还原。

## 比赛演示资料

新的演示包只导入客户原件、知识库和公司资产；**不预生成需求、报价、样品、订单或生产资料**。打开 Cases 后由你指挥 Agent 逐节点推进。

```powershell
backend/.venv/Scripts/python.exe demo/seed.py
```

会创建三条待办：

- `inq_demo_de`：Nordlicht Outdoor 定制通勤背包，含客户询盘、两家工厂报价、包装变更、PO、样品反馈、客户确认、内部批准、付款凭据和供应商确认原件。
- `inq_demo_mx`：Casa Verde 帆布袋试单，演示 300 件与 MOQ 500 的澄清。
- `inq_demo_uk`：信息不足的英国促销询盘，演示先澄清再推进。

演示路径：`询盘评估 → Tech Pack/BOM → 供应商报价与核价 → 客户报价 → 打样 → PO/PI 与付款 → 生产资料与放行`。每个节点由 Agent 通过工具读取原件、写成果或向用户提问；核价时在对话中明确汇率和毛利率（例如“汇率 7.20、毛利率 20%”），人工确认、付款核验和放行由界面单独记录。

知识库包含 8 篇通用业务规则（客户评估、箱包 Tech Pack、核价、贸易术语、打样、订单/PI、生产/验货、材料参考）和 3 份项目确认文档（Nordlicht / Casa Verde / Harbor，含客户确认人、规格补充和核价假设）。Agent 会优先用项目确认补全各案例缺项，再按节点加载对应 Skill。模型配置：

```dotenv
MODEL_API_KEY=...
MODEL_NAME=deepseek-flash
MODEL_BASE_URL=https://api.deepseek.com/v1
```

未配置模型时，Agent 工具不会伪造执行结果，会明确返回 `MODEL_NOT_CONFIGURED`。

## 验证

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests agent-kit/tests -q -p no:cacheprovider
npm run typecheck
npm run test
npm run build
```

可在 `backend/.env` 设置 `MODEL_API_KEY`、`MODEL_NAME` 和 `MODEL_BASE_URL` 启用 Agent 工具调用；未配置时不会伪造执行结果。正式商业批准、外部确认、付款核验和生产放行由服务端门禁控制，草稿下载不表示已发送或已开工。演示账号和默认密钥仅用于本机演示，不可公开部署。

## 开发与文档

根目录 npm workspaces 只包含 `fontend/`。直接执行 `npm run dev` 时，前端连接 `http://127.0.0.1:8000` 的 API；使用 `python dev.py` 可同时启动全部服务。前后端浏览器回归在 `fontend/` 执行 `npm run test:e2e`（会启动独立临时数据库）；Windows 默认使用已安装的 Edge，可用 `PLAYWRIGHT_BROWSER_PATH` 指定 Chrome/Edge 路径。

- [Workbench v2 契约：阶段、成果、工具与 Skill](doc/18-workbench-v2-contract.md)
- [当前 Hackathon PRD](doc/Navowork-PRD-v0.5--Hackathon删减版.md)
- [本轮合入、验收与剩余边界](doc/19-guilimao-prd-acceptance.md)
- [后端设计](doc/TradeWorkbench_Backend_Design_v1.0.md)
- [Agent 节点图](doc/TradeWorkbench_Agent_Node_Graph_v1.0.md)
- [前端接口说明](fontend/docs/INTEGRATION.md)
- [独立评测入口](evaluation/README.md)

本机画板演示与引用/资产回归使用 `npm run test:e2e:mock`，在 5175 端口运行，与真实服务回归分离。真实模式的询盘页可在「业务流程」和「资料画板」之间切换。
