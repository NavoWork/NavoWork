---
name: po-check
description: 逐字段核对买方 PO 与明确版本和状态的商业基准，保留买方原文、来源和差异定位。
---

这是 NavoWork 产品内资源，供主 Agent 加载；不安装为个人 Codex Skill。

处理 PO 核对、数量价格差异、贸易条款/港口冲突和 PI 前的商业一致性复核。使用宿主 Case 权限和不可变版本引用。需要 `case.read`、`sources.read`、`artifacts.read_version`；原始文件需要解析时还需 `sources.parse`。缺能力返回 blocked，缺事实保留 Unknown，不能补零或猜测接受状态。

1. 读取买方 PO 原件和当前允许使用的报价/商业条款版本。优先使用宿主确认的当前基准；不得把被替代版本当作当前版本。没有客户接受证据时仍可比较，但必须报告实际基准 version_id、status 与 `customer_acceptance_supported=false`；草稿/内部评审不是客户已接受。
2. 将双方字段整理为 `{value, raw, evidence}`：数量、单价、行金额、总数量、总金额、币种、贸易术语、指定地点、Incoterms 版本、付款、规格引用；同时核对买卖方、SKU/单位和交付原文。证据带 Case/source/locator/quote/role。港口字段须保存整句买方原文，例如 `FOB Shanghai, Incoterms 2020`，定位到页码和 Trade term 字段。不可只保留归一后的港口。
3. 用显式 line_id 对应双方行，不凭金额自动合并产品/颜色。数量和金额使用十进制字符串；数量不可为零。只允许大小写、空白的确定性归一，不转换币种、箱/件或改写付款条款。未知税费/附加费、复杂计价或行映射需交回已有工具，不能静默忽略；不重复计算报价。
4. 按 input.schema.json 调用 `order_skills.adapter.run("po_check", request, context, host)`。`compare_po` 检查已有单价乘数量、行合计和字段差异，不执行定价或审批。宿主验证引用、来源角色、客户接受范围/版本和 Case；缺客户接受、基准未发布、缺字段或不一致都保留 findings。
5. 报告实际比较基准及其状态、是否有客户商业接受证据、逐字段差异、买方原文和定位、缺项。匹配只表示所检查内容一致，不能表示已签约、已收款或已放行。客户新 PO 不自动取代旧商务条件，港口变化必须商务复核。

需要核对报告文件时，将结构化数据、引用和全部差异交给宿主通用文档草稿工具（适配层 create_file=True）。不得自动修正 PO 或生成外发、批准操作。缺文件工具明确 blocked。output.schema.json 描述 ToolResult.data；真实注册由主模块完成。
