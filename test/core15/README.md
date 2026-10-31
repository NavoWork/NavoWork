# 15 类核心业务文件 Mock

全部属于虚构模拟 Case `BAG-2026-DE-001`。这是 2026-10-31 的后续确认阶段，原测试包的缺项与阻断场景保持原样。

新增证据在 `evidence/`。按编号可逐份上传；不要把 `manifest.json` 或脚本当作原始客户资料上传。

| 编号 | 核心类别 | 实际文件 |
| --- | --- | --- |
| 01 | 客户档案 | [01_customer_profile](01_customer_profile.pdf) |
| 02 | 客户询盘（RFQ） | [02_customer_RFQ](02_customer_RFQ.pdf) |
| 03 | 询盘评估表 | [03_inquiry_assessment](03_inquiry_assessment.pdf) |
| 04 | 产品需求确认表 | [04_requirement_confirmation](04_requirement_confirmation.pdf) |
| 05 | 产品规格书（Tech Pack） | [05_techpack_V3](05_techpack_V3.pdf) |
| 06 | 包装与验货要求 | [06_packing_and_inspection](06_packing_and_inspection.pdf) |
| 07 | 客户需求确认记录 | [07_customer_confirmation_record](07_customer_confirmation_record.pdf) |
| 08 | 供应商报价单 | [08_supplier_quotation_V3](08_supplier_quotation_V3.xlsx) |
| 09 | 产品成本核算表 | [09_costing](09_costing.xlsx) |
| 10 | 客户报价单（Quotation） | [10_customer_quotation_V3](10_customer_quotation_V3.pdf) |
| 11 | 打样申请单 | [11_sample_request](11_sample_request.pdf) |
| 12 | 样品反馈及修改记录 | [12_sample_feedback_revision](12_sample_feedback_revision.pdf) |
| 13 | 最终样品确认书 | [13_final_sample_confirmation](13_final_sample_confirmation.pdf) |
| 14 | 订单成交文件（PO / PI / SC） | [14a_PO_DE-PO-2026-118-R2](14a_PO_DE-PO-2026-118-R2.pdf)、[14b_PI-26031-003](14b_PI-26031-003.pdf)、[14c_SC-26031-003](14c_SC-26031-003.pdf) |
| 15 | 最终订单技术附件 | [15_order_technical_annex_V3](15_order_technical_annex_V3.pdf) |

## 证据索引

| 简称 | 证据文件 |
| --- | --- |
| 历史源副本 | [original-inquiry.eml](evidence/original-inquiry.eml) |
| E01 | [closeout-customer-technical-confirmation.eml](evidence/closeout-customer-technical-confirmation.eml) |
| E02 | [closeout-factory-a-spec-cost-schedule-confirmation.eml](evidence/closeout-factory-a-spec-cost-schedule-confirmation.eml) |
| E03 | [closeout-internal-sample-measurement-s03.eml](evidence/closeout-internal-sample-measurement-s03.eml) |
| E04 | [closeout-customer-sample-approval-s03.eml](evidence/closeout-customer-sample-approval-s03.eml) |
| E05 | [closeout-finance-costing-basis.eml](evidence/closeout-finance-costing-basis.eml) |
| E06 | [closeout-manager-quotation-v3-price-approval.eml](evidence/closeout-manager-quotation-v3-price-approval.eml) |
| 历史源副本 | [original-change-color-box.eml](evidence/original-change-color-box.eml) |
| 历史源副本 | [original-customer-conditional-confirmation.eml](evidence/original-customer-conditional-confirmation.eml) |

共 6 封新增模拟确认邮件，另保留 3 份历史原始邮件的逐字节副本，便于脱离原目录单独回放。

## 阶段与门禁

- 最终规格 Tech Pack V3、报价 V3、样品 S03、PO R2、PI/SC 和技术附件 V3 相互引用。
- 60 mm LOGO、新彩盒规格、MOQ 与候选生产交期来自新增虚构确认邮件；不是从旧图片推测。
- 最终样品确认只批准 S03/Tech Pack V3/包装规格，不能代表货款到账或量产放行。
- PI 和 SC 为待签署草稿；量产仍因缺少订金到账证据与内部生产放行而阻断。
- 45 天到汉堡仍为客户目标。28 天为满足样品、订金、内部放行条件后的候选工厂生产期。

## 复建和校验

业务内容在 `../scripts/core15_content.json`，PDF/证据生成器为 `../scripts/build_core15.py`，Excel 生成器为 `../scripts/build_core15_sheets.mjs`。
使用 Codex bundled Python/Node（同上级 README）。先运行 PDF 生成器，再运行 Excel 生成器，最后运行 `../scripts/validate_core15.py`。
Excel 生成器通过 `CODEX_NODE_MODULES`（可选）定位 bundled `@oai/artifact-tool`，不会写入项目依赖目录。
重新生成两种文件后先执行 `validate_core15.py --seal` 绑定本次模拟版本哈希，此后执行不带参数的 `validate_core15.py` 只读检查。
