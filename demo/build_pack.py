"""Build the fictional competition materials. No external communications."""
from pathlib import Path
import json
from email.message import EmailMessage
from email.policy import SMTP

ROOT = Path(__file__).resolve().parent / "competition_v1"
ROOT.mkdir(parents=True, exist_ok=True)

def write(name, text):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")

def mail(name, sender, subject, text, date="Sat, 31 Oct 2026 09:00:00 +0800"):
    message = EmailMessage(policy=SMTP)
    message["From"] = sender
    message["To"] = "Alex <alex@navowork.example>"
    message["Subject"] = subject
    message["Date"] = date
    message["Message-ID"] = f"<{name.replace('/', '-')}@demo.example>"
    message.set_content(text, cte="8bit")
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(message.as_bytes())

DE_INQUIRY = """Dear Alex,
We are Nordlicht Outdoor GmbH, Germany. Please quote 3,000 custom backpacks,
style BP-DE-3000, for our outdoor retail stores. Target price: USD 9.50 per piece.
Please use black 600D polyester, 210D lining, a padded 15.6-inch laptop sleeve,
45 x 30 x 15 cm dimensions, and our white embroidered logo, 50 x 20 mm.
One plain kraft box per bag, 20 bags per export carton. FOB Ningbo, Incoterms 2020.
We would like them in Hamburg within 45 days if possible; please assess feasibility.
Please quote sample cost, production lead time and 30% deposit / 70% before shipment.
Product drawing and requested specifications are attached. No sample is approved yet.
Best regards, Michael Weber / procurement@nordlicht.example"""
CHANGE = """Dear Alex,
For BAG-2026-DE-001, please change the packaging from a plain kraft box to a custom
CMYK printed color box, 48 x 33 x 18 cm. Please keep the quantity at 3,000 backpacks,
the material, dimensions, logo and other product requirements unchanged.
Please provide the additional cost and lead-time impact before we approve the revision.
This request is not authorization to start production.
Michael Weber / Nordlicht Outdoor GmbH"""
MX_INQUIRY = """Hola Alex,
Somos Luna Comercio S.A. de C.V., Mexico City. We would like a trial order
of 300 canvas bags (帆布袋), style CT-MX-0600, natural cotton canvas 12 oz,
38 x 42 cm, handles 65 cm, single-color black screen-printed logo 8 x 8 cm.
Please quote FOB Ningbo, Incoterms 2020. We hope to receive the order in 30 days.
Please confirm MOQ and sample terms before a firm quote. Our target is USD 4.00 per bag.
Saludos, Sofia Hernandez / compras@luna.example"""
UNKNOWN = """Hello,
We are preparing a promotional project for next month and need a product carrying our logo.
Please suggest what information you need before providing a quotation.
The item type, purchase quantity, material, size, delivery destination and budget are not yet specified.
Emma Brown / hello@harbor.example"""

SPEC = {"product": "backpack", "sku": "BP-DE-3000", "quantity": 3000,
    "material": "600D polyester shell; 210D polyester lining", "dimensions": "45 x 30 x 15 cm; tolerance +/- 1 cm",
    "color": "black", "logo": "White embroidery, 50 x 20 mm, front pocket center; approved artwork required",
    "construction": "Padded 15.6-inch laptop sleeve; 2 side mesh pockets; padded adjustable straps",
    "packaging": "Plain kraft box per bag; 20 bags/carton", "inspectionStandard": "General inspection level II; AQL major 2.5 / minor 4.0; critical 0; agreed functional checks",
    "destination": "Hamburg", "incoterm": "FOB", "namedPlace": "Ningbo", "incotermsVersion": "2020",
    "missingFields": ["sampleApproval", "shippingSchedule"], "status": "draft", "simulation": True}
SPEC2 = {**SPEC, "packaging": "Custom CMYK color box 48 x 33 x 18 cm; 20 bags/carton; customer artwork CB-02",
         "missingFields": ["shippingSchedule"], "pendingReconfirmation": False}
MX_SPEC = {**SPEC, "product": "canvas bag", "sku": "CT-MX-0600", "quantity": 600,
    "material": "12 oz cotton canvas", "dimensions": "38 x 42 cm; handles 65 cm", "color": "natural",
    "logo": "One-color black screen print 8 x 8 cm", "construction": "Single compartment, reinforced handles",
    "packaging": "Paper band per bag; 100 bags/carton", "destination": "Mexico City",
    "missingFields": ["sampleApproval", "shippingSchedule"]}

WIKI = [
("01-demo-route", "业务流程｜从询盘到交付的工作顺序", "业务流程", """# 从询盘到交付
每次只处理当前指令涉及的环节。先读取当前询盘和已收到的材料，列明缺项，再生成对应成果。

1. 询盘：提取产品、数量、规格、目标价、目的地和交期；信息不足时准备澄清问题。
2. 产品：确认面料、尺寸、工艺、LOGO、结构与包装，制作规格书和工厂询价清单。
3. 报价：收到供应商原件后比较 MOQ、成本、周期；按明确汇率与毛利率核价。
4. 打样：制作打样要求，记录样品编号、反馈和修改，单独取得最终样确认。
5. 订单：核对 PO 与已确认报价，准备 PI 和技术附件，保留所有差异。
6. 生产：分别确认规格、报价、样品、双方订单、付款保障和供应商排期，再检查放行条件。
7. 验货与交付：依据当前规格整理检查项、异常和整改要求，交付信息以实际证据为准。

资产库中的文件按本轮指令选用。尚未收到的后续确认不能用于消除当前缺项；已生成草稿不能视为批准。
"""),
("02-bag-spec", "包袋产品｜规格与工艺确认清单", "产品资料", """# 包袋规格确认
## 必须明确的字段
款号、产品类型、数量、主面料成分与克重、里料、尺寸及公差、颜色、LOGO工艺与位置、拉链扣具、内袋结构、包装与验货标准。

背包需补充电脑隔层适配、肩带承重、侧袋结构和底部加固。帆布袋需补充面料盎司、提手长度、缝线和印刷色数。

## 规格书约定
每个字段保留来源与版本。图纸提供形状与尺寸参考，照片不能证明材质成分、精确尺寸或认证。
包装单独记录内包装、装箱数量、外箱尺寸、唛头和图稿版本。未经客户明确同意，不采用后续彩盒方案替换当前包装。

客户规格确认与实物样批准分别记录，客户说“价格可以”不等于已接受尺寸、LOGO或包装。
"""),
("03-cost", "核价规则｜汇率、毛利率与费用分摊", "业务流程", """# 成本与报价
单件总成本 CNY = 工厂基础价 + 单件包装 + 国内费用分摊。
报价 USD/件 = 总成本 ÷ 汇率(CNY/USD) ÷ (1 - 毛利率)。单价向上舍入至美分，再乘数量得到商品小计。
毛利率20%不等于成本加成20%。MOQ按当前客户确认数量检查，数量不足先询问供应商或客户。

## 成本依据
基础价、包装、MOQ、有效期和周期来自供应商当前报价。国内费用由内部费用记录支持；汇率和目标毛利由操作者明确提供。
供应商报价不自动确认汇率与毛利率。缺少成本字段保留待确认，不能用零补齐。

## 费用边界
FOB商品小计不包含未约定的海运、保险、目的国税费。打样与快递单列，不合并进大货金额。
报价单必须列币种、数量、单价、小计、付款、贸易术语、指定地点、有效期、生产起算条件。
"""),
("04-trade", "报价条款｜FOB与交期表达", "客户沟通", """# FOB 与交期
使用完整表达：FOB Ningbo, Incoterms 2020。指定装运港改变时重新复核国内费用和责任范围。
生产周期、出库安排、海运时间和到港日期分别记录。客户期望45天到汉堡是目标，未经船期核实不能写成承诺。

英文：Estimated production lead time starts after final sample/artwork approval and payment conditions are met. Arrival is subject to a separately confirmed shipping schedule.
西语：El plazo estimado de producción comienza después de aprobar la muestra y el arte final y de cumplir las condiciones de pago. La fecha de llegada requiere confirmar el transporte.

付款比例、报价有效期、样品费用及补充条款以双方当前约定为准。草稿发送前复核所有金额、单位、版本与缺项。
"""),
("05-change", "变更处理｜影响分析与版本维护", "业务流程", """# 变更处理
先保留客户变更原件，核对当前生效规格与报价，再列直接和下游影响。
包装变化可能影响规格书、工厂询价、成本、报价、样品、PO和生产资料。数量变化还需重查MOQ与费用分摊。

1. 记录变化字段、旧值、新要求与来源；未知的新成本和周期保留待确认。
2. 用工厂新报价重新核算，生成候选草稿版本，保留旧版。
3. 已存在的受影响成果关联实际修订；尚未开展的后续环节注明下一次生成时使用新版。
4. 所有影响处理完毕后再激活新基准；样品、客户规格和内部报价批准分别重新核对适用版本。

客户提出变更不等于接受额外费用、交期延长或授权生产。
"""),
("06-sample", "样品反馈｜修改、条件接受与最终确认", "产品资料", """# 样品反馈与确认
每次反馈绑定样品编号、规格版本、寄样批次和客户来件。
反馈分类：完整接受、部分接受、条件接受、拒绝。‘Looks good, but…’、需改LOGO或包装、待复样等都保留未关闭条件。

## 修改清单
逐项记录位置、现象、客户要求、责任人、拟修改内容和复验依据。尺寸测量、工厂检查和客户最终批准分别归档。
图片不能替代精确尺寸测量，内部测量通过不能替代客户接受。最终样批准必须覆盖指定样品与当前规格。

## 检查范围
尺寸公差、面料颜色、缝线、拉链、肩带、电脑隔层、印绣花、包装适配与唛头。AQL、功能测试和市场认证要求按双方约定和实际报告记录。
最终样已接受仍不意味着合同已签、订金已到账或量产已放行。
"""),
("07-order", "订单与生产｜PO核对、PI与放行条件", "业务流程", """# PO、PI 与生产
## PO核对
对照明确版本的报价，检查买卖方、SKU、单位、数量、单价、行金额、总额、币种、贸易术语、港口、付款、交期和规格引用。
保留买方原文及差异定位。FOB Shanghai与FOB Ningbo不是同一条款，不能静默归一。内部批准报价不等于客户已接受。

## PI准备
可在样品未批准时整理PI草稿，未知字段列为待确认；冲突保留双方值。草稿必须保留所用报价、PO、规格版本和待签署状态。

## 六项放行条件
客户最终规格确认、当前样品批准、内部商业报价批准、买卖双方确认同一订单、付款保障核验、供应商排期确认。
同时不得有未关闭的重大变更。每项分别核对来源与适用版本，上传付款凭据不自动记作到账。

## 核心业务档案
核心业务资料包含需求、Tech Pack V3、报价V3、样品S03、PO R2、PI/SC与技术附件。它们属于同一档案快照，仅在用户选择对应资料时使用。
样品S03的接受不覆盖其他样品；内部价格批准不覆盖生产放行。PI/SC待签署、订金证据缺失或内部放行未记录时，生产保持阻断。
"""),
("08-assets", "资料规范｜知识复用与原件引用", "团队协作", """# 资料与版本
知识库保存通用规则；资产库存放原件。具体客户要求、成本与确认以本项目收到并引用的证据为准。

文件按询盘、规格、报价、样品、订单、生产与验货分类。引用时固定文件版本和来源，后续上传不改变已完成工作的依据。
历史订单可供参考，不能自动继承其价格、交期、付款或批准。个人资产转入公司空间需由所有者明确操作。

可以将本次成果归档到资产库，将可复用经验保存为知识草稿。知识草稿审核发布后，才成为团队正式规则。
"""),
]

FILES = []
def record(key, name, role, cases, future=False):
    FILES.append({"key": key, "file": name, "role": role, "cases": cases, "future": future})

for key, title, folder, content in WIKI:
    write(f"wiki/{key}.md", content)

mail("sources/de-inquiry.eml", "Michael Weber <procurement@nordlicht.example>", "BAG-2026-DE-001 / 3,000 custom backpacks", DE_INQUIRY)
record("inquiry", "sources/de-inquiry.eml", "customer_request", ["de_a", "de_b", "de_c"])
for version, spec in ((1, SPEC), (2, SPEC2)):
    write(f"sources/spec-DE-v{version}.txt", "产品规格原件 - 未登记系统批准\n" + json.dumps(spec, ensure_ascii=False, indent=2))
    write(f"edits/spec-DE-v{version}.json", json.dumps(spec, ensure_ascii=False, indent=2))
    record(f"spec{version}", f"sources/spec-DE-v{version}.txt", "customer_request", ["de_a", "de_b", "de_c"] if version == 1 else ["de_b", "de_c"], version == 2)

offers = [
    {"key": "a1", "supplier": "工厂 A｜宁波远行箱包", "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28, "sheet": "Factory A V1", "cases": ["de_a", "de_b", "de_c"]},
    {"key": "b1", "supplier": "工厂 B｜绍兴行旅箱包", "baseCny": "46", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 23, "sheet": "Factory B V1", "cases": ["de_a", "de_b", "de_c"]},
    {"key": "a2", "supplier": "工厂 A｜彩盒新版", "baseCny": "44", "packagingCny": "5", "localCny": "4", "moq": 1000, "leadDays": 31, "sheet": "Factory A V2", "cases": ["de_b", "de_c"]},
    {"key": "mx1", "supplier": "工厂 M｜嘉兴帆布制品", "baseCny": "15", "packagingCny": "1", "localCny": "2.5", "moq": 500, "leadDays": 18, "sheet": "Factory M V1", "cases": ["mx"]},
]
for offer in offers:
    content = f"""SUPPLIER QUOTATION {offer['key'].upper()}
Supplier: {offer['supplier']}
Product: {'canvas bag CT-MX-0600' if offer['key']=='mx1' else 'backpack BP-DE-3000'}
Base factory cost: CNY {offer['baseCny']} per piece. Packaging: CNY {offer['packagingCny']} per piece, charged separately.
MOQ: {offer['moq']} pieces. Estimated production lead time: {offer['leadDays']} days after final sample/artwork and payment conditions.
Supplier currency: CNY. Valid until: 2026-11-14. No international freight or import tax included.
Packing: {'custom CMYK color box 48 x 33 x 18 cm, CB-02' if offer['key']=='a2' else 'paper band' if offer['key']=='mx1' else 'plain kraft box'}.
The workbook Supplier_Quotes.xlsx / {offer['sheet']} contains the same supplier quotation.
Domestic charges CNY {offer['localCny']}/piece are an internal allocation, not part of the supplier's factory quote.
Production starts only after the agreed prerequisites are confirmed."""
    write(f"sources/quote-{offer['key']}.txt", content)
    record("offer_"+offer["key"], f"sources/quote-{offer['key']}.txt", "supplier_quote", offer["cases"], offer["key"]=="a2")
mail("sources/customer-packaging-change.eml", "Michael Weber <procurement@nordlicht.example>", "Please revise packaging / no production authorization", CHANGE)
record("change", "sources/customer-packaging-change.eml", "customer_change", ["de_b", "de_c"], True)

final_approval = """I approve the final BP-DE-3000 specification with the CB-02 color box, 3,000 pieces, black 600D polyester and 210D lining, 45 x 30 x 15 cm, white embroidered logo 50 x 20 mm.
I approve sample SMP-DE-CB02 with seal DEMO-SEAL-02, the product and packaging artwork and the agreed inspection standard.
I accept quotation QT-DE-001-V2: USD 9.21 per piece, USD 27,630 goods total, FOB Ningbo Incoterms 2020, 30% deposit and 70% before shipment. Validity 2026-11-14.
Please retain our PO-DE-001-V2 as the buyer-confirmed order. This email confirms specification, sample and buyer order; it does not prove seller acceptance, bank receipt or production start."""
mail("sources/customer-final-approval.eml", "Michael Weber <procurement@nordlicht.example>", "Final spec, sample and buyer PO confirmation", final_approval)
record("customer_ok", "sources/customer-final-approval.eml", "customer_approval", ["de_c"], True)
mail("sources/seller-order-acceptance.eml", "Alex <alex@navowork.example>", "Seller confirms PO-DE-001-V2", "Seller NavoWork Trading confirms PO-DE-001-V2, BP-DE-3000 / 3,000 pieces / USD 9.21 / USD 27,630, FOB Ningbo Incoterms 2020, 30% deposit USD 8,289 and 70% balance USD 19,341. Final spec and CB-02 packaging apply. Arrival date remains subject to shipping confirmation. Production release remains conditional on all checks.")
record("seller_ok", "sources/seller-order-acceptance.eml", "internal_note", ["de_c"], True)
mail("sources/supplier-production-confirmation.eml", "Factory A <sales@factory-a.example>", "CB-02 production conditions confirmed", "We confirm the BP-DE-3000 final specification, approved sample SMP-DE-CB02, CB-02 color box and quantity 3,000. Base CNY44, packaging CNY5, MOQ1000. Estimated production 31 days after all final approvals and payment assurance. No substituted materials. We accept preparation for production under the final approved documents. This is not a notice that production has started.")
record("supplier_ok", "sources/supplier-production-confirmation.eml", "supplier_confirmation", ["de_c"], True)
write("sources/payment-advice.txt", """FINANCE RECONCILIATION ADVICE
Reference: DEMO-PAY-DE-001
Order: PO-DE-001-V2
Payer: Nordlicht Outdoor GmbH
Beneficiary: NavoWork Trading
Currency: USD
Goods total: 27630.00
Deposit rate: 30%
Amount to reconcile: 8289.00
Remaining amount: 19341.00
Record date: 2026-10-31
Payment receipt reference: pending finance verification.
Finance must verify the receipt and record a reconciliation against this reference.
Uploading this file alone must not create a verified payment or production release.
""")
record("payment", "sources/payment-advice.txt", "payment_receipt", ["de_c"], True)
write("sources/sample-inspection.txt", """SAMPLE INSPECTION / SMP-DE-CB02
Specification: BP-DE-3000 final color-box specification; seal DEMO-SEAL-02.
Dimensions 45 x 30 x 15 cm, tolerance +/-1 cm: within specified tolerance.
Black 600D shell / 210D lining; 15.6-inch sleeve; 2 mesh pockets: matches supplied specification.
White embroidered logo 50 x 20 mm; CB-02 color box 48 x 33 x 18 cm: within specified tolerance.
Workmanship, zipper travel, straps and packaging fit: inspection completed.
Inspection standard: General II, major AQL2.5/minor4.0/critical0 as agreed, not a certification claim.
Customer approval must be recorded separately using customer-final-approval.eml.
""")
record("sample_check", "sources/sample-inspection.txt", "sample_inspection", ["de_c"], True)
mail("sources/mx-inquiry.eml", "Sofia Hernandez <compras@luna.example>", "Trial order / 300 canvas bags", MX_INQUIRY)
record("mx_inquiry", "sources/mx-inquiry.eml", "customer_request", ["mx"])
mail("sources/mx-quantity-confirmation.eml", "Sofia Hernandez <compras@luna.example>", "Quantity update / 600 canvas bags", "We agree to increase the order to 600 canvas bags to satisfy MOQ. Material, size and logo remain unchanged. Please send a revised quotation. This confirms quantity only, not price, sample or shipment date.")
record("mx_quantity", "sources/mx-quantity-confirmation.eml", "customer_request", [], True)
write("sources/spec-MX-v1.txt", "QUANTITY 600 ONLY AFTER CUSTOMER UPDATE\n" + json.dumps(MX_SPEC, ensure_ascii=False, indent=2))
record("mx_spec", "sources/spec-MX-v1.txt", "customer_request", [], True)
mail("sources/uk-incomplete-inquiry.eml", "Emma Brown <hello@harbor.example>", "New promotional project / details needed", UNKNOWN)
record("uk_inquiry", "sources/uk-incomplete-inquiry.eml", "customer_request", ["uk"])
mail("sources/uk-clarification-reply.eml", "Emma Brown <hello@harbor.example>", "Clarification / 800 laptop bags", "We need 800 laptop bags (电脑包), 15.6-inch size, dark grey, with our logo. Material and detailed dimensions remain to be confirmed. Destination London. We have no approved sample or supplier quotation yet; please prepare a requirement checklist only.")
record("uk_reply", "sources/uk-clarification-reply.eml", "customer_request", [], True)

write("sources/product-reference.svg", '''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="680" viewBox="0 0 1000 680">
<rect width="1000" height="680" fill="#f3f5f8"/><g font-family="Arial" fill="#172b4d">
<text x="55" y="65" font-size="30">BP-DE-3000 / product specification drawing</text>
<text x="55" y="102" font-size="17">Requested dimensions. Not a photograph or measurement certificate.</text>
<path d="M390 195 C390 145 610 145 610 195" fill="none" stroke="#56647b" stroke-width="20"/>
<rect x="320" y="190" width="360" height="370" rx="65" fill="#263449"/>
<rect x="355" y="380" width="290" height="140" rx="22" fill="#40516a"/>
<path d="M350 285 L650 285 M375 405 L625 405" stroke="#92a4ba" stroke-width="5"/>
<rect x="447" y="420" width="106" height="42" fill="none" stroke="white" stroke-width="2"/>
<text x="460" y="448" fill="white" font-size="20">LOGO</text>
<path d="M260 190 V560 M250 190 H270 M250 560 H270 M320 600 H680 M320 590 V610 M680 590 V610" stroke="#314867" stroke-width="2"/>
<text x="170" y="380" font-size="24">45 cm</text><text x="455" y="638" font-size="24">30 cm</text>
<text x="725" y="290" font-size="20">Depth: 15 cm</text><text x="725" y="330" font-size="18">600D shell / 210D lining</text>
<text x="725" y="365" font-size="18">15.6-inch laptop sleeve</text><text x="725" y="400" font-size="18">White embroidery</text>
<text x="725" y="435" font-size="18">50 x 20 mm</text></g></svg>''')
record("drawing", "sources/product-reference.svg", "customer_request", [])

def make_pdf():
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    output = ROOT / "sources/PO-DE-001-V2.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=40, bottomMargin=40)
    blocks = [Paragraph("PURCHASE ORDER", styles["Title"]),
              Paragraph("PO-DE-001-V2 | Date: 2026-10-31 | Related quotation: QT-DE-001-V2", styles["Normal"]), Spacer(1, 18)]
    rows = [["Buyer", "Nordlicht Outdoor GmbH, Germany"], ["Seller", "NavoWork Trading, China"],
            ["Contact", "Michael Weber / procurement@nordlicht.example"], ["Delivery term", "FOB Ningbo, Incoterms 2020"],
            ["Product", "BP-DE-3000 custom backpack"], ["Quantity", "3,000 pieces"], ["Unit price", "USD 9.21 per piece"],
            ["Goods total", "USD 27,630.00"], ["Deposit (30%)", "USD 8,289.00"], ["Balance (70%)", "USD 19,341.00 before shipment"],
            ["Final sample", "SMP-DE-CB02 / seal DEMO-SEAL-02"], ["Packaging", "CMYK box 48 x 33 x 18 cm, artwork CB-02; 20 pcs/carton"]]
    table = Table([[Paragraph(a, styles["Normal"]), Paragraph(b, styles["Normal"])] for a, b in rows], colWidths=[120, 390])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf1f7")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#d8dfeb"))]))
    blocks += [table, Spacer(1, 18), Paragraph("Specification and execution conditions", styles["Heading2"])]
    for line in ["Black 600D polyester shell, 210D lining, 45 x 30 x 15 cm (+/-1 cm). Padded 15.6-inch laptop sleeve. White embroidered logo 50 x 20 mm.",
                 "Estimated production: 31 days after final sample/artwork approval, payment assurance and supplier confirmation. Hamburg arrival remains subject to a separately confirmed shipping schedule.",
                 "Sample fee USD 60 and courier USD 35 are separate. International freight, insurance and import taxes are excluded from this goods total.",
                 "Inspection: agreed General II, major AQL 2.5 / minor 4.0 / critical 0. Final specification and approved sample govern inspection.",
                 "Buyer and seller acceptance must be recorded separately. PO acceptance, payment receipt and production release are recorded separately."]:
        blocks += [Paragraph(line, styles["Normal"]), Spacer(1, 8)]
    doc.build(blocks)

SCENARIOS = [
    {"key": "de_a", "title": "德国定制背包询盘", "customer": "Michael Weber / Nordlicht Outdoor", "originalText": DE_INQUIRY, "destination": "Hamburg", "baseline": 0, "nextAction": "整理3,000件背包需求，确认规格与交期缺项", "prompt": "请先整理这封询盘的需求和待确认事项。"},
    {"key": "mx", "title": "墨西哥帆布袋试单", "customer": "Sofia Hernandez / Luna Comercio", "originalText": MX_INQUIRY, "destination": "Mexico City", "baseline": 0, "nextAction": "整理300件试单需求，确认MOQ与打样条件", "prompt": "请先整理客户需求，列出询价前需要确认的信息。"},
    {"key": "uk", "title": "英国品牌礼品采购", "customer": "Emma Brown / Harbor Promotions", "originalText": UNKNOWN, "destination": "London", "baseline": 0, "nextAction": "准备产品类型、数量和预算的澄清问题", "prompt": "请分析这封询盘，起草简洁的需求澄清问题。"},
]

if __name__ == "__main__":
    make_pdf()
    record("po", "sources/PO-DE-001-V2.pdf", "customer_po", ["de_c"], True)
    record("workbook", "sources/Supplier_Quotes.xlsx", "supplier_quote", [], False)
    manifest = {"version": "competition-v1", "simulation": True, "asOf": "2026-10-31", "wiki": [{"key": k, "title": t, "folder": f, "file": f"wiki/{k}.md"} for k,t,f,_ in WIKI], "files": FILES, "offers": offers, "scenarios": SCENARIOS, "spec1": SPEC, "spec2": SPEC2, "mxSpec": MX_SPEC}
    write("pack.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Prepared {len(WIKI)} Wiki documents and {len(FILES)} source files in {ROOT}")
