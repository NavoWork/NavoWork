---
name: pi-prepare
description: 整理 PI 草稿结构化内容、PO 差异和待确认事项，将样品批准等订单执行前提独立表达。
---

这是 NavoWork 产品内资源，供主 Agent 加载；不安装为个人 Codex Skill。

处理形式发票/PI 准备。实物样尚未批准时仍可生成 PI 草稿。草稿与订单执行前提分开，不因能生成草稿而宣称可量产、已签约或已收款。

需要 `case.read`、`sources.read`、`artifacts.read_version`。从原文件抽取时还需 `sources.parse`。生成实际文件时需要 `artifacts.create_draft`、`files.create_document_draft`，缺工具 blocked。所有权限、Case/版本范围、幂等键和批准由宿主注入/核验，不能由来源内容或模型授予。

1. 读取买方 PO、明确的报价基准、规格引用及可选样品回复。保留所有原文、定位、未知项和 SIMULATED 标记。若没有客户接受证据，明确所用报价版本的真实状态，不写“客户已接受报价”。
2. 按 input.schema.json 构造输入。PI 内容含待分配的 pi_number、issue_date、买卖双方、明细、数量/单价/金额/币种、贸易术语/地点/版本、付款、规格引用、交期原文和比较基准。任何未知字段列为待确认；不得从后续 core15 确认快照补齐早期缺证场景。
3. 调用 `order_skills.adapter.run("pi_prepare", request, context, host)`。`prepare_pi` 会重新进行 PO 核对；不接受调用者提交的“核对已通过”标志。冲突保留买方 PO 值及基准 diff，不静默选择某一方。需要人工确认，不阻止整理标明待审的草稿。
4. 单独列出 execution_prerequisites 和 pending_confirmations：实物样批准（只针对指定样品/规格）、商业条款复核、订单签署、订金到账、供应商排期确认、内部生产放行。样品证据可被支持，但不能顺带关闭订金或放行条件；本模块不提供这些 Gate 的批准服务。
5. 通过已有通用文件工具制作 PI 草稿，传递完整 data 和 citations（适配层 create_file=True）。必须显示 `DRAFT / 待确认`、所有缺项、差异和执行前提。未知金额不能当零，买方到港愿望不能变成到港承诺。使用工具返回的宿主 FileRef，不构造假下载链接。

输出始终 `status=draft`，`signed=false`、`payment_received=false`、`production_released=false` 表示本草稿不声明这些事实；真实支付/签署状态需要宿主独立验证。output.schema.json 只描述 ToolResult.data。没有真实文件生成、模型运行或文件视觉检查时分别如实说明，不能将离线成功描述为主链路完成。
