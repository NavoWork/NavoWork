# 05｜业务文件生成与交付：XLSX / DOCX / PDF

> Owner：后端文件工程师 ｜ 目标：产出**实际可编辑、可打印、可交付**的文件，而不把 Agent 文字当成业务成果。

## 1. 总设计

```text
Canonical Artifact Version (JSON + hash)
    ├── XLSX Renderer (openpyxl) → XLSX → 反向验收关键字段
    ├── DOCX Renderer (python-docx) → DOCX → PDF Renderer → PDF
    └── Delivery Packager → zip manifest + files + validation report
```

对外文件从**单一版本快照**生成，不能同时读取不同时点的“最新”来源。

## 2. 每类交付物的导出格式

| Artifact | 推荐主格式 | 可选格式 | 导出字段 |
|---|---|---|---|
| Requirement Brief / Tech Pack | XLSX 或 DOCX | PDF | SKU、尺寸已知/未知、材料、LOGO、包装、附件与版本 |
| Supplier RFQ | DOCX / 邮件草稿 | PDF | 采购要求、数量、交期询问、需要确认的问题 |
| Supplier Comparison | XLSX | PDF | 条款口径、币种、MOQ、费用、交期、差异标记 |
| Cost Sheet | XLSX | PDF | 数值与公式解释、汇率、毛利、成本项、来源 |
| Quotation | DOCX / PDF | XLSX | 客户、商品、数量、单价、币种、有效期、Incoterms 地点 |
| PI | DOCX / PDF | XLSX | 买卖方、订单行、支付条款、总额、交付约定 |
| Production Instruction / T&A | XLSX + DOCX | PDF | 数量分解、包装/LOGO、计划节点、版本、需确认项 |

## 3. Excel 生成策略

使用 `openpyxl` 由后端生成有样式的可编辑 `.xlsx`。MVP 先自定义模板，禁止直接假定用户上传任意复杂模板都能无损导入编辑后再导出。

**格式检查**：
- 金额列显示币种和小数位（内部精度和显示精度分离）。
- 每个数值列含单位；禁止出现“20”但不知是件还是箱。
- 条目含稳定 `item_id`，不依赖工作表行号确定字段。
- 同一文件内可以设置说明页展示 `artifact_version_id`、生成时间、来源与待确认项；正式对外报价不暴露内部成本和敏感来源。
- `openpyxl` 本身**不计算公式**：导出公式不能替代后端已经验证过的计算结果；不能依赖未缓存的 Excel 公式作为正式金额。

```python
from openpyxl import Workbook

def render_cost_sheet(data: dict, path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Costing"
    ws.append(["Item", "Cost (CNY/piece)", "Source"])
    for item in data["items"]:
        ws.append([item["label"], float(item["amount"]), item.get("source_assertion_id")])
    ws.append(["Total Cost", float(data["computed"]["total_cost_cny"]), "backend verified"])
    wb.save(path)
```

该代码是**接口示例**，生产实现需补齐单位格式、金额精度展示、数据校验、版本元数据、样式及异常路径。

## 4. DOCX/PDF 生成策略

- DOCX：使用命名模板，将 Canonical 字段映射到段落/表格；未确认项明确标为 `DRAFT / PENDING CONFIRMATION`。
- PDF：由 DOCX 或服务端排版工具生成；需固定字体部署、页面大小和版本页脚；**不能只检查 `file exists`**。
- 注意中英文/德文的字体嵌入或回退，长品名、表格跨页、货币符号、PDF 页眉页脚。
- 如客户提供专有模板，先定义字段映射和样例验收，**不要承诺通用 PDF 原位编辑**。

## 5. Artifact → 文件模板映射

```yaml
artifact_kind: quotation
schema_version: trade.quotation.v1
template: quotation_default.docx
field_mapping:
  customer_name: buyer.name
  quantity: lines[0].quantity
  unit_price_usd: lines[0].unit_price.amount
  incoterm: trade.incoterm.rule
  named_place: trade.incoterm.place
  validity_date: validity.expires_on
required_fields:
  - buyer.name
  - lines
  - trade.incoterm.rule
  - trade.incoterm.place
```

字段缺失时，**草稿可以带占位符**，但 `can_release=false`，并向 UI 返回准确字段路径。

## 6. 输出后的独立校验（不能忽略）

生成完成后做二次检查：

1. XLSX：重新打开工作簿并读取关键单元格，比较 Canonical 数值和条款。
2. DOCX：读取关键段落/表格文本，确认报价金额、数量、买卖方、版本与模板一致。
3. PDF：抽取文字（必要时渲染页面人工检查），确认未截断和关键金额未丢失。
4. ZIP：校验每个文件 SHA-256 与 manifest，构造下载列表。
5. 任意一步失败 → 返回 `EXPORT_VALIDATION_FAILED`，不显示“成功交付”。

**特别重要**：OpenXML 文件格式无损并不代表业务数据无误，校验必须面向业务字段。

## 7. Delivery Pack 的 Manifest

```json
{
  "delivery_id":"del_001",
  "case_id":"BAG-DE-001",
  "status":"exported",
  "items":[
    {"artifact_version_id":"quotation_v2", "filename":"Quotation-v2.pdf", "sha256":"..."},
    {"artifact_version_id":"pi_v1", "filename":"PI-v1.xlsx", "sha256":"..."}
  ],
  "warnings":["Production release pending"],
  "prepared_by_run_id":"run_014",
  "exported_at":"2026-10-31T09:30:00Z"
}
```

内部草稿包可含需确认清单与来源引用；对外客户包不得自动包含内部成本明细或供应商敏感报价。

## 8. 导出按钮的安全语义

- `Preview`：只读/可预览，可不创建正式交付记录。
- `Export Draft`：允许带水印/草稿标识导出，记录导出动作，不等于批准。
- `Release & Export`：严格经过 `QUOTE_RELEASE` 或其他适用 Gate，导出已批准版本。
- `Send`：P0 不实现；P1 接入真实外部渠道且单独审批。

## 9. 验收用例

- [ ] 规范 Case 可以输出 Spec、Costing、Quotation、PI、Production Instruction 至少 5 种实际文件。
- [ ] 所有导出文件包含明确版本、日期和适用草稿/发布状态。
- [ ] Cost Sheet 的原方案为 50 CNY → 8.69 USD；彩盒新方案 53 CNY → 9.21 USD。
- [ ] PDF 长文本不溢出或丢失关键信息；XLSX 金额格式、页眉与行项目无误。
- [ ] 下载 P0 未经批准草稿带 `DRAFT` 标签，不能显示 `RELEASED`。
- [ ] 已发布 v1 的导出在 v2 出现后仍可按原业务快照重现。
- [ ] 文件导出失败不会被 Agent 错标为“交付成功”。
