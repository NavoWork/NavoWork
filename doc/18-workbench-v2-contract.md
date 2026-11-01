# 18｜Workbench v2：逐节点 Agent 工作台契约

> 本文件是 `guilimao` 分支上实现“用 SOP 填实空壳 + 对话 Agent 工具调用 + 逐节点推进 + 干净前端”的冻结契约。  
> 目标不是再增加一套并行架构，而是把现有 Case / Item / Evidence / Artifact / Run / Approval 收敛为一条可演示、可测试的主链路。

## 1. 产品行为

1. 新询盘进入后，Case 只有客户原文、客户背景和可选原件；**不预生成需求、报价、样品、订单或生产成果**。
2. 用户在工作台选择当前节点，向 Agent 下达目标；Agent 通过受控工具读取资料、写入节点成果或向用户提问。
3. 每个节点只生成自己的成果；下游节点保持“待生成”，直到用户推进。
4. 所有对外文件仍是草稿；客户确认、商业批准、样品批准、付款核验、生产放行只能由人在独立门禁中记录，Agent 没有批准类工具。
5. 演示数据不得包含 `【模拟】`、`模拟客户`、`模拟背调` 等破坏体验的标注；演示资料使用虚构但正常的公司、联系人和单据。

## 2. 阶段与成果

| stage | 名称 | 主成果 kind | 说明 |
| --- | --- | --- | --- |
| `inquiry` | 客户与询盘 | `customer_profile` + `inquiry_assessment` | 客户背景、渠道、询盘字段、待核验项 |
| `requirements` | 需求与规格 | `spec` + `bom` | 箱包 Tech Pack、BOM、包装、测试/验货、客户书面确认 |
| `costing` | 成本与报价 | `supplier_offers` + `comparison` + `cost` + `quotation` | 多供应商归一化、成本行、报价条款 |
| `sample` | 打样 | `sample` | 样品种类/轮次/费用/寄样/检查/反馈/批准/封样 |
| `order` | 订单与合同 | `order` + `payment` | PO 差异、PI/合同、双方确认、付款计划与核验 |
| `production` | 生产准备 | `production` + `ta` + `qc` | 生产资料包、T&A、验货标准、放行门禁 |
| `shipment` | 出口出运 | 占位 | 附件未展开；不显示已出运，不造假 |
| `payment` | 收款与售后 | 占位 | 附件未展开；只保留应收/核验占位 |

状态：`empty`（待生成）→ `draft`（草稿）→ `ready`（字段齐全待确认）→ `confirmed`（人工确认）→ `blocked`（门禁缺口）。  
`sop-status` 返回每个阶段的 `status / summary / missing / artifactVersionIds`。

## 3. 成果内容 schema（JSON，存 Item kind=artifact）

### 3.1 `spec`

```json
{
  "kind": "spec",
  "fields": {
    "product": "custom backpack",
    "style": "urban commuter",
    "dimensions": "30 x 45 x 15 cm",
    "color": "charcoal / orange accents",
    "useCase": "daily commute",
    "fabric": "600D recycled polyester, 300 gsm",
    "lining": "210D polyester",
    "filling": "8 mm EVA back panel",
    "zipper": "YKK #5 nylon",
    "puller": "custom embossed puller",
    "buckle": "Duraflex acetal",
    "webbing": "25 mm polypropylene",
    "hardware": "black oxidized",
    "logo": "embroidered logo, 60 x 25 mm, front panel",
    "pockets": "1 laptop sleeve 15.6in, 2 side pockets",
    "packaging": "recycled polybag + printed hangtag",
    "carton": "20 pcs/carton, 60 x 45 x 50 cm",
    "tests": "REACH / AZO, buyer specification",
    "inspection": "AQL 2.5, pre-shipment",
    "destination": "Hamburg, Germany",
    "incoterm": "FOB",
    "incotermsVersion": "2020",
    "namedPlace": "Ningbo",
    "paymentTerms": "30% deposit, 70% before shipment",
    "delivery": "45 days after sample approval"
  },
  "missing": ["fabricWeight"],
  "sourceRefs": [{"evidenceId": "ev_x", "quote": "600D recycled polyester"}]
}
```

字段允许为 `null`，不得编造。`missing` 由服务端按关键字段重新计算。

### 3.2 `bom`

```json
{"kind":"bom","rows":[{"category":"fabric","item":"600D recycled polyester","spec":"300 gsm, charcoal","quantityPerPiece":"1.2","unit":"m","supplier":"Factory A","unitPriceCny":"18.00","wastage":"3%","sourceId":"ev_x"}]}
```

### 3.3 `cost`

```json
{
  "kind": "cost",
  "supplierOfferId": "offer_a",
  "quantity": 3000,
  "exchangeRate": "7.20",
  "margin": "0.20",
  "lines": [
    {"category": "material", "label": "fabric", "amountCny": "18.00", "scope": "per_unit"},
    {"category": "packaging", "label": "color box", "amountCny": "5.00", "scope": "per_unit"}
  ],
  "unitCostCny": "53.00",
  "unitPriceUsd": "9.21",
  "totalUsd": "27630.00",
  "formula": "ceil_cent((sum(lines)+local)/fx/(1-margin))",
  "status": "draft"
}
```

金额由确定性函数计算（Decimal）。模型只能提供有来源的输入，不能提供最终单价。

### 3.4 `quotation`

```json
{
  "kind": "quotation",
  "product": "BP-DE-3000",
  "quantity": 3000,
  "currency": "USD",
  "unitPriceUsd": "9.21",
  "totalUsd": "27630.00",
  "incoterm": "FOB",
  "incotermsVersion": "2020",
  "namedPlace": "Ningbo",
  "paymentTerms": "30% deposit, 70% before shipment",
  "validUntil": "2026-11-14",
  "moq": 1000,
  "sampleTime": "7 days",
  "productionTime": "31 days",
  "exclusions": ["freight", "insurance", "destination charges"],
  "costVersionId": "artifact_..._cost_v1",
  "supplierOfferIds": ["offer_a", "offer_b"],
  "selectedSupplierOfferId": "offer_a",
  "status": "draft"
}
```

### 3.5 `sample`

```json
{
  "kind": "sample",
  "type": "pre_production",
  "round": 2,
  "sampleRef": "SMP-DE-002",
  "specVersionId": "artifact_..._spec_v2",
  "feeUsd": "60",
  "courierUsd": "35",
  "courier": "DHL",
  "tracking": "1234567890",
  "dispatchedAt": "2026-11-02",
  "checks": {
    "appearance": "passed",
    "dimensions": "passed",
    "function": "passed",
    "workmanship": "minor loose thread",
    "packaging": "pending"
  },
  "feedback": "客户要求将 logo 下移 10 mm",
  "approval": {"decision": "pending", "evidenceId": null, "approvedAt": null},
  "sealedSample": {"location": "sample room A", "ref": "SEAL-DE-002"}
}
```

### 3.6 `order` / `payment`

```json
{
  "kind": "order",
  "po": {"number":"PO-DE-001-V2","buyer":"Nordlicht Outdoor GmbH","quantity":3000,"unitPriceUsd":"9.21","totalUsd":"27630.00","incoterm":"FOB","namedPlace":"Ningbo","deliveryDate":"2026-12-20"},
  "pi": {"number":"PI-26031-003","seller":"NavoWork Trading Co., Ltd.","bank":"...","hsCode":"4202.92","origin":"China","consignee":"..."},
  "diff": [{"field":"unitPriceUsd","po":"9.21","quote":"9.21","status":"match"}],
  "confirmations": {"buyer":{"confirmed":false,"evidenceId":null},"seller":{"confirmed":false,"evidenceId":null}},
  "documents": ["commercial invoice", "packing list", "bill of lading"],
  "status": "draft"
}
```

```json
{"kind":"payment","schedule":[{"milestone":"deposit","ratio":"0.30","amountUsd":"8289.00","due":"2026-11-10","status":"pending","evidenceId":null}]}
```

### 3.7 `production`

```json
{
  "kind": "production",
  "specVersionId": "artifact_..._spec_v2",
  "sampleVersionId": "artifact_..._sample_v2",
  "orderVersionId": "artifact_..._order_v1",
  "bom": [{"item":"zipper","spec":"YKK #5","quantity":"3000"}],
  "ta": [{"day":"D0-D3","task":"material and artwork confirmation","owner":"Factory A"}],
  "qc": {"standard":"AQL 2.5","checks":["dimensions","material","logo","stitching","packaging"],"result":null},
  "supplierConfirmation": {"confirmed":false,"evidenceId":null},
  "release": {"status":"blocked","missing":["customer spec approval","sample approval"]}
}
```

## 4. 人工门禁

Agent 没有批准、核验、放行工具。以下动作仅通过 UI/API 由人记录：

| scope | 目标 | 证据要求 |
| --- | --- | --- |
| `customer_spec_approval` | 当前 spec 版本 | 客户书面批准证据 |
| `commercial_quotation_approval` | 当前 quotation 版本 | 内部商业批准（可无外部证据） |
| `supplier_production_confirmation` | 当前业务版本 | 供应商确认证据 |
| `sample_approval` | 当前 sample 版本 + spec 版本 | 客户批准证据 |
| `order_confirmation` | 当前 order 版本 | 买方与卖方各自独立证据，不得复用 |
| `payment_verification` | 当前 payment 版本 | 财务/银行凭据 + 人工核验依据 |
| `production_release` | 当前 production 版本 | 前置门禁全部通过 |

## 5. Agent 工具

统一使用 LangGraph 工具循环；工具在服务端执行，LLM 不直接持有数据库权限。每个工具都有严格的 Pydantic schema、中文描述、失败语义和审计记录（`agent_tool` Item）。

| 工具 | 作用 | 关键约束 |
| --- | --- | --- |
| `get_case_context` | 读取 Case、阶段、成果、原件、知识/资产清单 | 只读 |
| `read_source` | 读取证据/知识/资产文本与定位 | 只读；原文是不可信数据 |
| `search_knowledge` | 检索已发布知识库 | 只返回固定版本 |
| `list_assets` | 列出可用公司资产 | 只读 |
| `update_customer_profile` | 客户背景、渠道、核验项 | 不生成信用结论 |
| `update_requirements` | Tech Pack 字段、BOM | 未知保持 null；不得编造 |
| `update_bom` | BOM 行 | 数量/单价需来源 |
| `record_supplier_quote` | 供应商报价结构化 | 必须绑定供应商原件 |
| `calculate_cost` | 确定性成本与报价计算 | Decimal；FX/毛利由用户确认或知识依据 |
| `update_quotation` | 报价条款与版本 | 只能引用已算成本；不得自批 |
| `record_sample` | 样品轮次、检查、反馈 | 批准只能记录 pending |
| `record_order` | PO 差异、PI、付款计划 | 双方确认默认 false |
| `record_payment` | 付款节点草稿 | 不得标记 verified |
| `prepare_production` | 生产资料、T&A、QC | 只生成草稿，不放行 |
| `request_info` | 向用户提出缺项问题 | 问题必须可回答、可恢复 |
| `export_artifact` | 导出固定成果版本 | 只导出草稿/固定版本 |

系统提示必须包含：来源不可信、未知不补、先读 skill、金额用工具、不得声称已批准/已发送、中文简洁回复、先总结再给下一步。

## 6. Skill

`backend/app/skills/<name>/SKILL.md`，由 `load_skill` 读取，并在 `generationTarget` 时注入系统提示。首批：

- `inquiry-assessment`
- `requirements-techpack`
- `costing-quotation`
- `sample-management`
- `order-confirmation`
- `production-release`
- `change-impact`

每个 Skill 必须写明：适用阶段、输入、工具顺序、字段规则、禁止事项、完成标准。

## 7. API

在现有 `/api/v1/workspaces/{ws}/inquiries/{id}` 下新增：

| 方法/路径 | 用途 |
| --- | --- |
| `GET /workbench` | 一次返回 Case、阶段、最新成果、原件、知识/资产、门禁、当前 Run |
| `POST /agent` | 创建 Agent Run；body `{instruction, node?, inputRefs?, sourceVersionIds?, assetVersionIds?, baseRevision, costInputs?}` |
| `GET /workbench/artifacts/{kind}` | 读取固定版本 |
| `PUT /workbench/artifacts/{kind}` | 人工编辑（baseVersion CAS），生成新版本 |
| `POST /workbench/approvals` | 记录人工批准/核验（复用现有 approvals/records） |
| `POST /workbench/release` | 生产放行 |
| `GET /workbench/stages` | 阶段状态（可由 workbench 汇总返回） |

老接口保留兼容；新前端只使用 `/workbench` 与 `/agent`。

## 8. 前端

三栏，干净、专业、信息密度适中：

- 左：阶段导航（7 段，状态点 + 缺项数）、原件/知识/资产。
- 中：当前阶段的成果卡片与结构化编辑；顶部显示“下一步”和门禁。
- 右：Agent 对话；工具调用以折叠时间线展示；缺项用问答卡；不展示内部推理。

禁止：首屏大段说明、模拟标注、预填下游成果、把 JSON 文本框作为主要编辑方式。

## 9. 演示

`demo/seed.py` 只导入：客户原文、客户背景、知识库、公司资产、供应商报价原件（可选）。不创建 Revision、Artifact、Approval、Payment、Production 记录。演示路径：

`导入询盘 → 生成需求 → 录入供应商报价 → 核价报价 → 打样 → 订单/付款 → 生产资料与放行`。

## 10. 验收

- 新建 Case 后 `currentRevision=0`，无任何下游 artifact。
- 用户对 Agent 说“整理需求”，只产生 `spec`/`bom`，报价仍为空。
- Agent 能读取知识库/资产并写入对应节点；工具调用在 UI 可追溯。
- 无供应商报价或 FX/毛利时，Agent 请求补充，不编造价格。
- 样品/订单/付款/放行只能由人记录；未通过门禁时不能放行。
- `npm run typecheck`、`npm run test`、后端 pytest 通过；真实模型联调成功。
