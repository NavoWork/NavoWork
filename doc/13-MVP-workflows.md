# 13｜Hackathon MVP 三条端到端工作流：工程执行合同

> Owner：产品/Agent/后端/前端联合 ｜ **本文应直接成为端到端测试和 Demo 脚本的依据**。  
> 使用模拟 Case `BAG-DE-001`。三条 Flow 相互衔接，不要生成彼此独立、无法复用的“演示文档”。

## 0. Demo 的统一事实（所有数字均为演示假设）

- 客户：德国 Michael Weber；产品：OEM 定制背包；数量：3,000 pieces。
- 条款：FOB Ningbo, Incoterms® 2020；客户希望约 45 天内到汉堡，**不是已被确认的到港承诺**。
- 原包装：普通纸盒；客户后续要求升级为定制彩盒。
- Supplier A：基础工厂价 CNY 44，包装 CNY 2，本地费用 CNY 4，单位成本 CNY 50，预计工厂生产时间 28 天。
- Supplier B：基础工厂价 CNY 46，包装 CNY 2，本地费用 CNY 4，单位成本 CNY 52，预计工厂生产时间 23 天。
- 演示汇率：7.20 CNY/USD；目标毛利：20%。
- 原报价：A `$8.69/件`，B `$9.03/件`；彩盒新包装价 A CNY 5，新成本 CNY 53，新建议报价 `$9.21/件`。
- 假设 Supplier A 通过导入文件确认了彩盒价格，但**彩盒 MOQ 和交期是否变化另需核实**。

## Flow A：询盘到可交付报价草稿

### 输入与用户动作

用户上传：`inquiry.eml`、`backpack-front.png`；先不上传成本文件。Agent 提出未知项与询价材料。随后导入 `supplier-A.xlsx` 与 `supplier-B.pdf`。

### 任务执行步骤（每步都应该持久产生结果引用）

| Step | 具体 Tool | 输入 | 输出与状态 | 核验 |
|---|---|---|---|---|
| A1 | `parse_source` | inquiry.eml / image | 源 Span/可观察要素 | 不推断未知材料/尺寸 |
| A2 | `extract_requirements` | source spans | Requirement Draft + Unknown List | 来源定位正确 |
| A3 | `create_spec_draft` | 当前已知事实 | Tech Pack Draft | 尺寸/等级未知字段显式存在 |
| A4 | `build_supplier_rfq` | Tech Pack Draft | RFQ Draft | 未知项保留询问 |
| A5 | `parse_source` + `normalize_supplier_quotes` | 两家报价 | Supplier Comparison Draft | 币种/费用范围/交期可比性 |
| A6 | `calculate_quote` | 采购成本 + 汇率/毛利策略 | Cost Sheet | A=8.69、B=9.03 |
| A7 | `create_quotation_draft` | Cost Sheet + 已知商务条款 | Quotation Draft | 草稿，而非客户已接受报价 |
| A8 | `validate_artifact` | Quotation Version | findings + Gate | 必填参数完备、发布另审批 |
| A9 | `export_artifact` | Draft Version | XLSX/DOCX/PDF | 关键数字二次验证 |

### 阻断节点

- 未得到具体包装成本：A6 返回 `MISSING_FACT`；允许仅完成 A1～A4 和“待成本数据”提示。
- 用户输入“从图片准确测量背包尺寸”：允许描述图像可观察内容，必须声明不能准确测量，不生成假尺寸。
- 用户要求“立即发出正式报价”：P0 无外部发送，展示完整的邮件草稿及导出动作；不能显示 `sent`。

### 可复现成果

`Requirement Brief v1`, `Tech Pack Draft v1`, `RFQ Draft v1`, `Supplier Comparison v1`, `Cost Sheet v1`, `Quotation Draft v1`。

## Flow B：包装变更 → 跨 Artifact 差异 → 审批

### 输入与用户动作

追加客户邮件：`change-packaging.eml`：“Please switch from plain box to a custom color box. Keep the delivery target if possible.”；初始**不提供彩盒供应商新报价**。

### 执行合同

1. `detect_change`：提取 `spec.packaging.type=custom_color_box`，关联邮件 Source Span；客户请求不自动成为生产已批准规格。
2. `analyze_impact`：至少识别 Tech Pack、RFQ、BOM/Cost Sheet、Quotation、生产指令的关联或潜在影响。
3. `propose_artifact_patch`：创建 Tech Pack V2 与 RFQ V2 候选；Cost Sheet 中包装成本设为待确认，不将旧包装价视作新价。
4. `validate_artifact`：阻止正式 Quotation V2 发布，解释缺 `supplier_packaging_cost` 与 `supplier_lead_time_confirmation`。
5. 用户导入 `supplier-A-color-box-update.xlsx`，明确新包装单价 CNY 5；解析为新断言并经过核实。
6. `calculate_quote`：新成本 53，新报价 9.21；创建 Cost Sheet V2 / Quotation V2 **草稿**。
7. UI 展示字段 Diff：普通纸盒→定制彩盒；成本 50→53；报价 8.69→9.21；包装供应商交期仍待确认。
8. 用户 `Apply to Draft`，写入新草稿；**不是自动批准正式报价**。
9. 内部价格负责人（模拟角色需显式标记）审批 `QUOTE_RELEASE` 对应准确 Quotation Version；如还有其他发布硬阻断则继续不放行。
10. `Production Instruction` 保留当前已发布依据与 `stale / needs_review` 提示，不能因为报价已批准就自动执行包装变更生产。

### 必须可见的失败画面

**先故意不上传彩盒报价**，让 Agent 显示“已完成可以做的工作，哪些被阻断”；补上数据后才重新计算。比 Demo 一路没有错误更能证明产品的可靠性。

### 至少 3 个修改目标

- `Tech Pack`: 包装字段显示 V2 Proposed。
- `Cost Sheet`: 新成本 53 CNY（引用新供应商价格）。
- `Quotation`: 新报价 9.21 USD（等待内部审核/已按具体审批发布）。

可选第 4 个：`Supplier RFQ`: 彩盒样式/尺寸/MOQ/交期确认要求。

## Flow C：客户 PO → PI / 生产资料包

### 输入与用户动作

用户上传客户 PO，指定其引用的报价版本。建议构造两个 PO：

- `po-correct.pdf`：数量 3,000、单价 $9.21、FOB Ningbo、包装定制彩盒；与候选新报价一致。
- `po-mismatch.pdf`：数量 3,200 或单价 $8.69；系统必须显示冲突。

### 具体执行步骤

| Step | Tool | 输出 | Gate |
|---|---|---|---|
| C1 | parse PO | PO 断言，带原始页码 | 不能假设客户邮件与 PO 必然一致 |
| C2 | compare_po_to_quote | 数量、价格、币种、术语、规格版本差异 | 异常需澄清 |
| C3 | generate_pi_draft | PI Draft + 金额汇总 | 不自动声称 PI 已签发 |
| C4 | build_production_pack_draft | 生产指令 / BOM / T&A 候选 | 缺时间/产能可标 Pending |
| C5 | validate_artifact(PRODUCTION_RELEASE) | 发布门禁结果 | 缺客户样品/工厂确认时阻断 |
| C6 | prepare_delivery | 可下载草稿 ZIP + manifest | 未批准必须标 DRAFT |

### 验收的关键冲突

- PO 的 3,200 与已批准 3,000 冲突，Agent 生成差异与澄清草稿，不自动生成“已确认订单”。
- 产前样没有客户批准，允许生产指令草稿但不能 `production_released=true`。
- `FOB Ningbo` 不证明 45 天抵达汉堡能够实现；需要工厂和物流证据。

## 4. 每条 Flow 的完成条件

| Flow | 真正可验收的 Done | 不能当成 Done |
|---|---|---|
| A | 文件真实生成、数字可重算、来源可跳转、草稿能编辑 | 模型输出一篇报价文字 |
| B | 三份工件新草稿、版本/差异/阻断完整、旧版保留 | 只改一个显示文本 |
| C | PO 差异报告、PI/生产资料草稿、审批门禁、下载 | 模拟用户点击=工厂已开工 |

## 5. 截图 / 演示所需交互

建议演示顺序：

1. 左边是用户原始邮件、附件；中间正在编辑的 Cost Sheet；右边 Agent 执行。
2. 让用户看到 A 供应商与 B 供应商的数值及来源，展示 `A = $8.69` 不是聊天猜测。
3. 突然输入彩盒变更，系统**先阻断**；引入新供应商报价后自动重算并输出 Diff。
4. 用户试图直接“发布生产资料”，因缺客户样品批准被阻断。
5. 最终导出草稿包（或具备真实证据的已批准文件包），保留审计与版本。

## 6. 随后可以做的延展（不纳入 P0 承诺）

- 打样与样品批准记录、实际生产进度日报、质检异常与整改、装箱单和商业发票、收款/售后。
- 每一个扩展都应该是新增 Artifact Schema + Tool + Gate + Evals，而不是重做一套独立 Agent 和业务数据库。
