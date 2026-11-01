# NavoWork 真实文件资产与工作流演示包

基于 `origin/guilimao` 的 `d853ddf`，对照 `doc/Navowork-PRD-v0.5--Hackathon删减版.md` 和当前前后端实现制作。全部客户、价格、报价、样品与确认均为虚构；日期基线为 2026-11-01。

## 已经准备什么

- 默认导入 **65 个真实文件资产**：64 个公司资产、1 个个人资产。包含 36 PDF、10 XLSX、11 EML、5 PNG、1 SVG、1 TXT、1 Markdown。
- 其中 48 个是本轮新增资料，17 个是原 `test/core15` 的独立 Weber 历史快照。新主线采用 `BP-DE-3000-DEMO`，不会把 Weber 的藏蓝背包、织标、5 个/箱、S03 确认合并到 Nordlicht 的灰色通勤背包。
- 清单另外引用原 `test/inputs` 中 18 个回归输入，默认不导入；包括恶意邮件等负例。ZIP 中共 83 个业务来源文件，保留其真实后缀和字节。
- 7 个独立 Case、30 份初始 Case 原件、8 篇通用业务知识。后续事件原件按步骤追加；来源文件的存在不会建立应用里的审批、成本成果或生产放行。
- 15 类核心文件全部覆盖；订单类包含独立 PO、PI、SC。另补完整 V1/V2 Tech Pack、逐行 BOM、两家供应商原生报价、两种成本工作簿、竞品来源、LOGO、产品示意、BOM 图像和冲突 PO。

业务文件位于 `assets/`。`manifest.json` 是路径、哈希、空间、角色和演示步骤索引，`sheet_content.json` 是重建中间数据；这两个 JSON 不要当客户来源上传。

## 画板节点本地模拟（2026-11-01）

`node-simulations.json` 补充了五套路演案例的竞品摘要、设计方向和六步生产计划。德国背包的竞品源文件复用本包 `competitor_a.pdf`、`competitor_b.pdf`；运行时校验清单哈希，并将 PDF 原件及可定位摘录登记到当前询盘。其余四类竞品为新补充的虚构对比资料。

画板顺序为：客户原始询盘 → 客户需求与规格 → 竞品分析 → 产品设计图 → 方案与报价 → 风险与待确认项 → 双语回复 → 打样与确认 → 订单与合同 → 生产准备。初始化仍只显示原文和空的需求节点，每次保存后露出下一个空节点。

节点按钮走 `/workbench/simulations`，所有阶段本地生成；生图节点读取 `backend/app/assets/demo-images/` 中已准备的 PNG，不请求模型服务。只有右侧 AI 对话发送使用真实 Agent。每个节点保留业务版本，左侧文件夹包含节点数据和对应原件，生产准备下包含 T&A 和 QC。

当前“新建询盘”德国背包使用 `backend/app/demo_scenarios.py` 的完整海军蓝背包基线。仅复用本包的竞品快照，不把本包灰色背包的 V2 彩盒变更、不同样品号或 USD 9.21 价格混入当前询盘。订单金额与付款计划按当前已保存报价生成；审批与放行保持人工操作。

## 当前功能和文件能怎么用

| 功能 | 前后端入口 | 适用素材与实际边界 |
| --- | --- | --- |
| 公司/个人资产库 | `StaticLibrary.tsx`、`workspace_api.library_routes` | 登记 Blob 后显示真实大小、类型与下载地址；个人资产按账户隔离 |
| Case 原件和角色 | 工作台“项目资料”、`sop_api` evidence | PDF/XLSX/EML/PNG 等按真实文件上传；角色必须是后端枚举，不能直接使用旧 oracle 的命名 |
| 询盘与客户摘要 | 询盘节点、customer profile | OEM、ODM、新款、低 MOQ、缺项各有独立 Case；源文件不等于模型已经执行 |
| 规格/BOM/核价 | 规格与成本节点、domain/workbench API | `05_techpack_V1.pdf`、`bom_V1.xlsx`、供应商 XLSX；非零成本应绑定本 Case 实际 evidence ID |
| 原生文件编辑 | Case 内“文件编辑器”、`workbench/office` | 正向 BOM 和基础成本表可以建立工作副本、编辑和重算；资产库的 XLSX 卡片本身仅下载，不提供表格内容预览 |
| 竞品研究 | research 面板、`research/sources` | 两份 PDF 快照有虚构 URL、日期、范围和可定位原文；零售价不是自家成本 |
| 样品/规格确认 | 打样与审批入口 | 修改意见与最终样品确认分开；原件导入不自动登记批准，也不授权量产 |
| PO/PI | 订单节点 | 匹配 PO、冲突 PO、样品前 PI 请求独立进入；没有客户接受证据时使用“待协商依据” |
| 变更联动 | propagation、字段/版本绑定 | 源文件名不是绑定关系；先通过实际操作建立规格、BOM、成本、报价及依赖，才能演示联动。任意上传的工作簿不是天然纳管的成本成果 |
| 导出 | `workbench/artifacts/{kind}/export` | 实际 API 验证 PDF/XLSX/DOCX 导出字节；这些运行时输出没有预先伪装成 Agent 成果 |

### 表格的具体兼容性

**当前网页编辑器可编辑：** `bom_V1.xlsx`、`bom_V2.xlsx`、`supplier_A_V1.xlsx`、`supplier_A_V2.xlsx`、`supplier_B_V1.xlsx`、`09_costing_editable.xlsx`、旧 `core15/08_supplier_quotation_V3.xlsx`。

**可保存、下载、读取缓存，但网页编辑器会以 422 拒绝：** 本包 `09_costing.xlsx`、`bom_missing_price.xlsx`、旧 `core15/09_costing.xlsx`。它们使用 `IF/AND/COUNT` 等缺项保护公式，超出当前基础公式求值器的支持范围。这是当前实现的兼容边界，文件不是损坏的 XLSX。完整 Excel 中可使用带保护的成本表；网页演示选 `09_costing_editable.xlsx`。

基础成本表适配当前数值公式子集，业务输入仍须核对。编辑包装 `B8: 2 → 5` 会使 `B2: 8.69 → 9.21`、`B3: 26070 → 27630`。工作副本的变更不会自动成为客户接受或审批事实。

PDF 下载和文本提取已经验证；在 Codex 内嵌浏览器中，资产库的 PDF iframe 实测为空白，未将其记作预览通过。可下载后用 PDF 阅读器打开；全部新 PDF 已用 Poppler 逐页渲染检查。

## 已导入本机

本轮在默认本地配置中创建/补充了 `backend/data/navowork.sqlite3` 和 `backend/storage/` 的 Blob 文件。它们是忽略文件，不随 Git 同步。账户沿用应用的演示账户；没有修改账号配置。

同步代码后，新机器需要执行导入；**只拷贝 SQLite、缺少其中 Blob 路径对应的 storage 文件，无法得到可下载资产。** 导入脚本从本包原始文件重新登记，避免依赖同伴机器上的绝对路径。

在仓库根目录执行：

```powershell
# 只检查清单和计划，默认不写库
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py

# 追加导入现有 APP_ENV=demo 数据库；保留已有 Case 和成果
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply

# 或独立数据库（应用也需使用相同的 DATABASE_URL / STORAGE_ROOT）
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --database backend/data/assets-demo.sqlite3
```

可重复运行：相同字节不会产生重复资产或原件。已有同 ID 来源变更或存储损坏时会报错，不静默覆盖。`--refresh-unused-sources` 只用于素材作者在 Case 尚未产生运行/成果/事实/审批时修订来源，资产保留旧版本与 Blob，原件保留历史 Blob；已有业务使用则拒绝。正式演示不要使用此参数。

正常启服务仍用仓库 `start.ps1` / `start.bat` / `dev.py`；前端须为 `VITE_API_MODE=real`，API 与 Worker 必须使用同一个数据库和 storage。模型、图像服务凭据需按应用现有配置提供。本轮环境没有模型/图像凭据，未伪造在线 AI 成功。

## 演示路线

| Case | 初始输入 | 建议目标 |
| --- | --- | --- |
| `inq_assets_oem` | 完整可核价规格、BOM、供应商报价、核价假设 | 复核并核价，不强制研究或生图 |
| `inq_assets_odm` | RFQ、规格、11 行 BOM、A/B 报价、基础成本表、PNG LOGO | 条件报价和打样准备，再演示彩盒变更 |
| `inq_assets_design` | 新款构想、2 份竞品快照、示意图/LOGO | 研究与设计方向，成本缺失则不做正式报价 |
| `inq_assets_moq` | 客户 300 件，工厂 MOQ 500 且未报价 | 澄清并保留数量差异，不把客户改为 500/600 件 |
| `inq_assets_unknown` | 仅产品大类、LOGO 意向和“尽快” | 提问和英文回复草稿，不编造数量和价格 |
| `inq_assets_order` | PO、候选报价、包装要求 | 从 W2 独立进入，核对条款、准备 PI 草稿 |
| `inq_assets_pi_first` | 先开 PI 的请求、V1 条件报价、规格 | 不等待最终样品批准即可准备 PI；付款与量产仍待核验 |

先打开 `inq_assets_odm`，用 Case 的建议目标推进节点。主线默认是 11 份原件，不含后续客户批准。需要演示某个事件时，在仓库根目录追加：

```powershell
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_odm colorbox
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_odm sample_feedback
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_odm spec_approval
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_odm sample_approval
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_order conflicting_po
& backend/.venv/Scripts/python.exe test/scripts/seed_workbench_demo.py --apply --event inq_assets_order negotiation
```

刷新/重新进入 Case，在“项目资料”勾选新增原件后再给 Agent 当前目标。`sample_approval` 只追加模拟证据；若要登记批准，仍须由操作者在应用中明确绑定实际样品与规格版本。文中的 `TP-NL-V1/V2` 是来源文档标识，不能替代应用自动生成的 artifact ID/version/hash。

主线核价：制造 44 + 普通包装 2 + 本地分摊 4 = CNY 50，按汇率 7.20、毛利率 20% 向上舍入到美分为 USD 8.69；替换包装为 5 后为 CNY 53、USD 9.21，总额 USD 27,630。订金应付 8,289，尾款应付 19,341；应付不代表已收。报关和检验费用未知，报价保持条件性。

彩盒包装使用 47 × 32 × 17 cm，2 个/外箱，外箱 50 × 35 × 38 cm，共 1,500 箱；只通过尺寸/容积预检，实际装箱净空、强度与毛重仍待实测。原 seed 的 20 个彩盒装入 60 × 45 × 50 cm 外箱是不可能配置，保留在旧来源与冲突例中供核对，见 `AUDIT.md`。

## 验证与剩余事项

```powershell
& backend/.venv/Scripts/python.exe test/scripts/validate_workbench_demo.py --api
& backend/.venv/Scripts/python.exe test/scripts/validate_fixtures.py
& backend/.venv/Scripts/python.exe test/scripts/validate_core15.py
```

第一条使用临时 SQLite/storage 运行真实鉴权 API：文件哈希下载、7 个空成果 Case、重复导入、原件上传、10 份工作簿兼容性、基础成本表编辑重算、版本冲突、两轮业务核价、多格式导出、研究来源定位、事件幂等、私有资产和 Case 隔离。不会向开发库写入测试成果。报告位于 `test/.qa/workbench_demo/validation.json`。

另已运行前端类型检查、30 项前端单测、44 项相关后端测试。这些检查和数据适配通过不代表真实模型的完整 W1/W2 已跑通。尚需配置真实模型/图像服务后验证 Agent 全流程、VLM 行识别与人工复核、真实概念图生成及与当前规格绑定；示意 PNG 没有冒充 AI 生成图或实物样品。

旧素材验证曾因 Windows 检出转换失败：已按既有 SHA 恢复 5 个 PDF 和 3 封历史邮件的原始字节；`test/.gitattributes` 固定二进制/邮件字节。没有修改原事实或重封哈希。维护脚本 `repair_legacy_fixture_bytes.py` 默认只读，只有候选字节匹配原哈希且差异仅为换行时才允许恢复。

同伴的数据库未包含在 Git 跟踪内容中。本轮导入前本机只找到两组 `file-tools-e2e` SQLite，每组 1 个 Case、1 个 Blob，没有资产行；不能把这些临时库当成完整演示资产库。代码中的 `demo/seed.py` 另有 3 个资产的导入逻辑；它没有登记现成的 PDF/XLSX。
