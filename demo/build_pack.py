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
    message["Subject"] = "[SIMULATED / DEMO] " + subject
    message["Date"] = date
    message["Message-ID"] = f"<{name.replace('/', '-')}@demo.example>"
    message.set_content("SIMULATED BUSINESS RECORD - competition exercise only.\n\n" + text, cte="8bit")
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(message.as_bytes())

DE_INQUIRY = """Dear Alex,
We are Nordlicht Outdoor GmbH (fictional), Germany. Please quote 3,000 custom backpacks,
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
Michael Weber / Nordlicht Outdoor GmbH (fictional)"""
MX_INQUIRY = """Hola Alex,
Somos Luna Comercio S.A. de C.V. (fictional), Mexico City. We would like a trial order
of 300 canvas bags (帆布袋), style CT-MX-0600, natural cotton canvas 12 oz,
38 x 42 cm, handles 65 cm, single-color black screen-printed logo 8 x 8 cm.
Please quote FOB Ningbo, Incoterms 2020. We hope to receive the order in 30 days.
Please confirm MOQ and sample terms before a firm quote. Our target is USD 4.00 per bag.
Saludos, Sofia Hernandez / compras@luna.example"""
UNKNOWN = """Hello,
We are preparing a promotional project for next month and need a product carrying our logo.
Please suggest what information you need before providing a quotation.
The item type, purchase quantity, material, size, delivery destination and budget are not yet specified.
Emma Brown / hello@harbor.example (fictional company)"""

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
("01-demo-route", "比赛演示｜三条主链路与资料使用", "业务流程", """# 比赛演示路线
全部客户、供应商、订单和财务记录均为模拟，日期基准为 2026-10-31。

## 五个待办
01 德国背包首次报价：从零开始，报价 A 为 USD 8.69/件，商品小计 USD 26,070。
02 德国彩盒变更续办：已有原包装报价 V1；修改成本和受影响成果，彩盒价 USD 9.21/件。
03 德国 PO 与生产放行：已有彩盒报价和规格 V2；六项确认待人工登记。
04 墨西哥帆布袋试单：客户先要 300 件，供应商 MOQ 500；先确认增至 600 件再核价。
05 英国信息不足询盘：缺产品类型和数量，演示 Agent 澄清、刷新恢复、继续处理。

## 操作约定
首页进入新画板，右侧对话处理；业务资料与审批链接进入原件、报价、成果编辑、变更及门禁工作台。
每个画板的“00 演示操作卡”给出可直接粘贴的指令和对应文件。
知识参考只约束通用规则，客户条件必须引用当前询盘原件。原件已上传不等于已批准。
“后续阶段”文件是剧本材料，在相应环节再登记为业务证据。
完整人工操作及命令补助手册见 demo/competition_v1/演示操作手册.md。
"""),
("02-bag-spec", "包袋产品｜背包与帆布袋规格确认清单", "产品资料", """# 包袋规格确认
适用：背包、帆布袋。以下产品是比赛模拟款，不能视为通用商品库存。

## BP-DE-3000 背包
600D 涤纶主面料、210D 里布，黑色；尺寸 45×30×15 cm，公差 ±1 cm。
15.6 英寸电脑隔层，两个侧网袋，可调节加垫肩带；白色刺绣 LOGO 50×20 mm。
拉链型号、织带规格、辅料色差和商标文件应在打样前确认，不能从效果图推断。
原包装为单件普通牛皮纸盒，20 件/箱。彩盒方案为 48×33×18 cm，CMYK，图稿 CB-02。

## CT-MX-0600 帆布袋
12 oz 棉帆布，本白色，38×42 cm，手提带 65 cm；单色黑色丝印 8×8 cm。
纸腰封包装，100 件/箱。模拟 MOQ 500，300 件的客户初始要求不满足该门槛。

## 必须确认
材料成分、厚度/克重、尺寸公差、颜色、LOGO 工艺与位置、辅料、内袋结构、包装、验货和认证。
图纸是规格沟通材料；客户书面确认和最终样品确认分别记录，不能用知识条目替代。
来源：spec-DE-v1.txt / spec-DE-v2.txt / spec-MX-v1.txt（本包模拟原件）。
"""),
("03-cost", "核价规则｜汇率、毛利率、费用与舍入", "业务流程", """# 确定性成本核价
适用本次模拟数据；不是企业完整 FOB 成本模板。
单件总成本 CNY = 工厂基础价 + 单件包装 + 国内费用分摊。
报价 USD/件 = 总成本 ÷ 汇率(CNY/USD) ÷ (1 - 毛利率)，最后向上舍入到美分。
毛利率 20% 不等于成本加成 20%。先舍入单价，再乘数量得商品小计。

| 方案 | 基础 | 包装 | 国内费用 | 汇率 | 毛利率 | 单价 USD | 数量 | 小计 USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A 原纸盒 | 44 | 2 | 4 | 7.20 | 20% | 8.69 | 3000 | 26070 |
| B 原纸盒 | 46 | 2 | 4 | 7.20 | 20% | 9.03 | 3000 | 27090 |
| A 彩盒 | 44 | 5 | 4 | 7.20 | 20% | 9.21 | 3000 | 27630 |
| MX 600 件 | 15 | 1 | 2.5 | 7.20 | 25% | 3.43 | 600 | 2058 |

费用分摊由内部成本记录承担，供应商原件只对基础价、包装和供应商周期负责。
汇率为演示假设，非实时汇率；运费、保险、税费未核实，不能填成零或承诺到港总价。
所有建议报价仍需内部商业批准。报价有效期、付款、术语版本和指定地点必须完整。
"""),
("04-trade", "报价条款｜FOB 宁波与交期表达", "客户沟通", """# FOB 与交期
本包使用 FOB Ningbo, Incoterms 2020。报价应明确术语、版本和指定装运港。
FOB 装运港交货不等于到港承诺。海运、保险及进口税费范围需另外书面约定。
客户要求 45 天到汉堡属于期望，不是经核实的承诺。
供应商 A 原包装预计 28 天、彩盒 31 天；B 原包装预计 23 天。
周期从客户最终样品/图稿确认、定金保障与工厂生产条件均满足后计算。
报价有效至 2026-11-14；付款建议 30% 定金、70% 出运前，经客户同意后记录。
英文：Estimated production lead time is 31 days after final sample/artwork approval and payment conditions are met. Arrival in Hamburg is subject to a separately confirmed shipping schedule.
西语：El plazo estimado de producción comienza después de aprobar la muestra y el arte final y de cumplir las condiciones de pago. La fecha de llegada requiere confirmar el transporte.
"""),
("05-change", "变更 SOP｜包装变更影响与版本维护", "业务流程", """# 包装变更处理
收到变更邮件先保留为 observed，再创建 ChangeSet。客户提出变化不意味着批准成本或生产。
彩盒变更：单件包装 CNY 2 → 5，国内分摊仍 4，工厂基础仍 44，报价 8.69 → 9.21 USD。
3000 件商品小计 26070 → 27630 USD，增加 1560 USD；供应商周期 28 → 31 天。
不能覆盖 V1，必须生成候选修订。检查规格、RFQ、成本、报价、样品、订单和生产资料的依赖。
候选成本/报价暂时留空是正确阻断，需要依据供应商新报价核算后保存新版本。
逐节点维护：直接影响关联新成果；下游尚未生成的 PO/生产资料可说明不修改既有成果，后续须使用新版本。
“记录复核”只是记录，不足以激活。关联经过人工编辑的候选成果并处理所有节点后才激活。
激活后重新核价，必要审批重新登记；客户规格、内部报价、样品和供应商确认分别处理。
"""),
("06-sample", "打样与验货｜封样、规格和检查标准", "产品资料", """# 打样与验货
德国背包模拟样品费 USD 60，快递 USD 35；都不包含在大货商品小计中。
原样预计 5 天，彩盒样预计 7 天；最终样编号 SMP-DE-CB02，封样标识 DEMO-SEAL-02。
客户批准需说明最终规格版本、产品样、颜色、LOGO 图稿、彩盒图稿和验货标准。
本例使用一般检验水平 II，主要缺陷 AQL 2.5、次要缺陷 AQL 4.0、致命缺陷零接受。
样品检查覆盖尺寸、外观、缝线、拉链、肩带、电脑隔层、印绣花、包装适配。
上述为双方模拟约定，不代替目的市场的强制测试要求。没有报告不得宣称通过 REACH 等认证。
sample-inspection.txt 是检查记录，customer-final-approval.eml 才是客户书面确认；两者用途不同。
"""),
("07-order", "订单与生产｜PO、PI、付款及六项放行门禁", "业务流程", """# 订单及生产放行
模拟 PO-DE-001-V2：3000 件 BP-DE-3000，USD 9.21/件，总额 USD 27630。
30% 定金 USD 8289，70% 尾款 USD 19341。样品与快递费另行结算。
核对双方主体、款号、规格/包装版本、数量、单价、币种、条款、交货地、付款节点和文件版本。

## 六项独立记录
1. 客户批准最终规格成果版本，证据角色 customer_approval。
2. 客户批准最终样品并绑定同一规格版本。
3. 内部批准包含完整成本与条款的报价版本。
4. 买卖双方分别确认同一 PO；买方证据 customer_approval，卖方 internal_note。
5. 责任人核验付款保障；payment_receipt 仅为原件，人工核验说明必填。
6. 供应商确认当前业务版本可生产；证据 supplier_confirmation。
同时不得存在未关闭重大变更。文件下载、客户说“OK”、银行凭据上传都不能替代以上记录。
本包 payment-advice.txt 明确为模拟财务记录，不是银行真实水单。完成演练也不能宣称真实到账或开工。
"""),
("08-assets", "资料规范｜知识、原件、历史订单与权限", "团队协作", """# 资料与版本
Wiki 保存可复用的规则和产品说明；资产库存放原文件。具体客户要求和成本来自当前 Case 的证据。
公司空间共享。个人资料不能静默转为公司资料；业务引用需要使用公司空间授权文件。
历史订单只能用于参考，价格、交期、包装和批准不能跨项目自动复用。
任务提交时固定 sourceVersionIds、assetVersionIds、供应商报价和证据；后续上传不改变已排队任务。
资料状态区分草稿、已发布和失效；已被任务引用的版本不覆盖，更新另建版本。
本包 EML/PDF/XLSX 是人工编写的模拟原件；图示明确为示意图，不是实物或认证证据。
在公司资产库查看全部阶段材料；当前 Case 只登记对应阶段已收到的材料。
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
    write(f"sources/spec-DE-v{version}.txt", "SIMULATED / 产品规格原件 - 未登记系统批准\n" + json.dumps(spec, ensure_ascii=False, indent=2))
    write(f"edits/spec-DE-v{version}.json", json.dumps(spec, ensure_ascii=False, indent=2))
    record(f"spec{version}", f"sources/spec-DE-v{version}.txt", "customer_request", ["de_a", "de_b", "de_c"] if version == 1 else ["de_b", "de_c"], version == 2)

offers = [
    {"key": "a1", "supplier": "工厂 A｜宁波远行箱包（模拟）", "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28, "sheet": "Factory A V1", "cases": ["de_a", "de_b", "de_c"]},
    {"key": "b1", "supplier": "工厂 B｜绍兴行旅箱包（模拟）", "baseCny": "46", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 23, "sheet": "Factory B V1", "cases": ["de_a", "de_b", "de_c"]},
    {"key": "a2", "supplier": "工厂 A｜彩盒新版（模拟）", "baseCny": "44", "packagingCny": "5", "localCny": "4", "moq": 1000, "leadDays": 31, "sheet": "Factory A V2", "cases": ["de_b", "de_c"]},
    {"key": "mx1", "supplier": "工厂 M｜嘉兴帆布制品（模拟）", "baseCny": "15", "packagingCny": "1", "localCny": "2.5", "moq": 500, "leadDays": 18, "sheet": "Factory M V1", "cases": ["mx"]},
]
for offer in offers:
    content = f"""SIMULATED / SUPPLIER QUOTATION {offer['key'].upper()}
Supplier: {offer['supplier']}
Product: {'canvas bag CT-MX-0600' if offer['key']=='mx1' else 'backpack BP-DE-3000'}
Base factory cost: CNY {offer['baseCny']} per piece. Packaging: CNY {offer['packagingCny']} per piece, charged separately.
MOQ: {offer['moq']} pieces. Estimated production lead time: {offer['leadDays']} days after final sample/artwork and payment conditions.
Supplier currency: CNY. Valid until: 2026-11-14. No international freight or import tax included.
Packing: {'custom CMYK color box 48 x 33 x 18 cm, CB-02' if offer['key']=='a2' else 'paper band' if offer['key']=='mx1' else 'plain kraft box'}.
The workbook Supplier_Quotes.xlsx / {offer['sheet']} contains the same simulated original quote.
Domestic charges CNY {offer['localCny']}/piece are an internal allocation, not part of the supplier's factory quote.
No actual production has started; this document is a training fixture."""
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
mail("sources/seller-order-acceptance.eml", "Alex <alex@navowork.example>", "Seller confirms PO-DE-001-V2", "Seller NavoWork Demo Trading confirms PO-DE-001-V2, BP-DE-3000 / 3,000 pieces / USD 9.21 / USD 27,630, FOB Ningbo Incoterms 2020, 30% deposit USD 8,289 and 70% balance USD 19,341. Final spec and CB-02 packaging apply. Arrival date remains subject to shipping confirmation. Production release remains conditional on all checks.")
record("seller_ok", "sources/seller-order-acceptance.eml", "internal_note", ["de_c"], True)
mail("sources/supplier-production-confirmation.eml", "Factory A <sales@factory-a.example>", "CB-02 production conditions confirmed", "We confirm the BP-DE-3000 final specification, approved sample SMP-DE-CB02, CB-02 color box and quantity 3,000. Base CNY44, packaging CNY5, MOQ1000. Estimated production 31 days after all final approvals and payment assurance. No substituted materials. We accept preparation for production under the final approved documents. This is not a notice that production has started.")
record("supplier_ok", "sources/supplier-production-confirmation.eml", "supplier_confirmation", ["de_c"], True)
write("sources/payment-advice.txt", """SIMULATED FINANCE ADVICE - NOT A BANK DOCUMENT
Reference: DEMO-PAY-DE-001
Order: PO-DE-001-V2
Payer: Nordlicht Outdoor GmbH (fictional)
Beneficiary: NavoWork Demo Trading (fictional)
Currency: USD
Goods total: 27630.00
Deposit rate: 30%
Amount to reconcile: 8289.00
Remaining amount: 19341.00
Simulation date: 2026-10-31
No real bank, account, SWIFT code or payment transaction is represented.
During the exercise the operator may record a simulated reconciliation, explicitly citing this reference.
Uploading this file alone must not create a verified payment or production release.
""")
record("payment", "sources/payment-advice.txt", "payment_receipt", ["de_c"], True)
write("sources/sample-inspection.txt", """SIMULATED SAMPLE INSPECTION / SMP-DE-CB02
Specification: BP-DE-3000 final color-box specification; seal DEMO-SEAL-02.
Dimensions 45 x 30 x 15 cm, tolerance +/-1 cm: simulation check passed.
Black 600D shell / 210D lining; 15.6-inch sleeve; 2 mesh pockets: matches supplied specification.
White embroidered logo 50 x 20 mm; CB-02 color box 48 x 33 x 18 cm: simulation check passed.
Workmanship, zipper travel, straps and packaging fit: inspected in the fictional scenario.
Inspection standard: General II, major AQL2.5/minor4.0/critical0 as agreed, not a certification claim.
Customer approval must be recorded separately using customer-final-approval.eml.
""")
record("sample_check", "sources/sample-inspection.txt", "sample_inspection", ["de_c"], True)
mail("sources/mx-inquiry.eml", "Sofia Hernandez <compras@luna.example>", "Trial order / 300 canvas bags", MX_INQUIRY)
record("mx_inquiry", "sources/mx-inquiry.eml", "customer_request", ["mx"])
mail("sources/mx-quantity-confirmation.eml", "Sofia Hernandez <compras@luna.example>", "Quantity update / 600 canvas bags", "We agree to increase the order to 600 canvas bags to satisfy MOQ. Material, size and logo remain unchanged. Please send a revised quotation. This confirms quantity only, not price, sample or shipment date.")
record("mx_quantity", "sources/mx-quantity-confirmation.eml", "customer_request", [], True)
write("sources/spec-MX-v1.txt", "SIMULATED / QUANTITY 600 ONLY AFTER CUSTOMER UPDATE\n" + json.dumps(MX_SPEC, ensure_ascii=False, indent=2))
record("mx_spec", "sources/spec-MX-v1.txt", "customer_request", [], True)
mail("sources/uk-incomplete-inquiry.eml", "Emma Brown <hello@harbor.example>", "New promotional project / details needed", UNKNOWN)
record("uk_inquiry", "sources/uk-incomplete-inquiry.eml", "customer_request", ["uk"])
mail("sources/uk-clarification-reply.eml", "Emma Brown <hello@harbor.example>", "Clarification / 800 laptop bags", "We need 800 laptop bags (电脑包), 15.6-inch size, dark grey, with our logo. Material and detailed dimensions remain to be confirmed. Destination London. We have no approved sample or supplier quotation yet; please prepare a requirement checklist only.")
record("uk_reply", "sources/uk-clarification-reply.eml", "customer_request", [], True)

write("sources/product-reference.svg", '''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="680" viewBox="0 0 1000 680">
<rect width="1000" height="680" fill="#f3f5f8"/><g font-family="Arial" fill="#172b4d">
<text x="55" y="65" font-size="30">BP-DE-3000 / simulated product drawing</text>
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
    blocks = [Paragraph("PURCHASE ORDER", styles["Title"]), Paragraph("SIMULATED - competition exercise only", styles["Heading2"]),
              Paragraph("PO-DE-001-V2 | Date: 2026-10-31 | Related quotation: QT-DE-001-V2", styles["Normal"]), Spacer(1, 18)]
    rows = [["Buyer", "Nordlicht Outdoor GmbH (fictional), Germany"], ["Seller", "NavoWork Demo Trading (fictional), China"],
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
                 "Buyer and seller acceptance must be recorded separately. This simulated PO is not a signed contract, a payment receipt or a production-start notice."]:
        blocks += [Paragraph(line, styles["Normal"]), Spacer(1, 8)]
    doc.build(blocks)

SCENARIOS = [
    {"key": "de_a", "title": "01｜德国背包首次报价【模拟】", "customer": "Michael Weber / Nordlicht Outdoor", "originalText": DE_INQUIRY, "destination": "Hamburg", "baseline": 0, "nextAction": "核对需求并选择工厂 A，生成 USD 8.69 报价草稿", "prompt": "请分析3000件背包需求，列出缺失信息；参考核价规则，先不承诺45天到港。"},
    {"key": "de_b", "title": "02｜德国彩盒变更续办【模拟】", "customer": "Michael Weber / Nordlicht Outdoor", "originalText": DE_INQUIRY, "destination": "Hamburg", "baseline": 1, "nextAction": "处理彩盒变更：包装2→5元，报价8.69→9.21美元", "prompt": "包装从普通纸盒改为定制彩盒，请分析受影响节点；以工厂A新版报价为依据。"},
    {"key": "de_c", "title": "03｜德国PO与生产放行【模拟】", "customer": "Michael Weber / Nordlicht Outdoor", "originalText": DE_INQUIRY, "destination": "Hamburg", "baseline": 2, "nextAction": "核对PO/样品/双方确认/付款保障；逐项解除六项门禁", "prompt": "请核对PO-DE-001-V2与彩盒最终规格及报价，准备生产资料草稿；不要自动批准或宣称开工。"},
    {"key": "mx", "title": "04｜墨西哥帆布袋试单【模拟】", "customer": "Sofia Hernandez / Luna Comercio", "originalText": MX_INQUIRY, "destination": "Mexico City", "baseline": 0, "nextAction": "先澄清300件低于MOQ500，再按客户600件回复核价", "prompt": "请分析300件帆布袋询盘，MOQ为500件，先生成澄清问题，不要承诺30天到货。"},
    {"key": "uk", "title": "05｜英国信息不足询盘【模拟】", "customer": "Emma Brown / Harbor Promotions", "originalText": UNKNOWN, "destination": "London", "baseline": 0, "nextAction": "通过Agent澄清产品和数量；刷新后继续同一个任务", "prompt": "请分析这封询盘，缺少哪些关键需求需要先问客户？"},
]

if __name__ == "__main__":
    make_pdf()
    record("po", "sources/PO-DE-001-V2.pdf", "customer_po", ["de_c"], True)
    record("workbook", "sources/Supplier_Quotes.xlsx", "supplier_quote", [], False)
    manifest = {"version": "competition-v1", "simulation": True, "asOf": "2026-10-31", "wiki": [{"key": k, "title": t, "folder": f, "file": f"wiki/{k}.md"} for k,t,f,_ in WIKI], "files": FILES, "offers": offers, "scenarios": SCENARIOS, "spec1": SPEC, "spec2": SPEC2, "mxSpec": MX_SPEC}
    write("pack.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Prepared {len(WIKI)} Wiki documents and {len(FILES)} source files in {ROOT}")
