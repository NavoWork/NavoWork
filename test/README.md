# TradeWorkbench Hackathon Demo Fixtures

本目录提供可上传的模拟输入、结构化期望结果、确定性校验器，以及对接当前应用的资产与 Case 导入脚本。全部姓名、公司、报价、订单和审批均为虚构演示数据。邮件地址使用 `.invalid` 域名。资料上的 `SIMULATED` 标记不可移除或表述为真实商业记录。

## 当前前后端演示包（2026-11-01）

请优先使用 [workbench_demo/README.md](workbench_demo/README.md)：对照 Hackathon PRD v0.5 和 `guilimao` 当前代码，补齐 15 类文件、逐行 BOM、研究快照、异常输入及 7 条独立演示路线；默认登记 65 个真实 PDF/XLSX/EML/PNG 等资产和 Case 原件。下载包为 `NavoWork_demo_assets.zip`。资产库登记、Case 证据与实际业务成果分别处理，导入不会冒充审批或生成结果。

旧包仍用于历史快照和回归。原 `core15/09_costing.xlsx` 可下载和读取，但其保护公式超出当前网页编辑器支持范围；网页演示使用新包的 `09_costing_editable.xlsx`。具体适配结论、实际 API 检查与尚未执行的在线模型检查见新包说明。

## 15 类核心业务文件补充包

完整索引见 [core15/README.md](core15/README.md)。按用户的标准化清单补齐 15 类，提供 17 份实际业务文件（15 份 PDF、2 份 XLSX；订单类含独立 PO、PI、SC），另附 6 封新增模拟确认邮件和 3 份历史来源副本。

该包使用 `BAG-2026-DE-001` 在 `2026-10-31` 的后续确认快照：TechPack V3、Quotation V3、Sample S03、PO R2 与技术附件 V3 关联。它不会覆盖下方原演示里缺少样品/供应商确认的阻断快照。样品批准只对指定版本与范围生效，PI/SC 待签署、订金到账和内部量产放行仍待确认。

`scripts/validate_core15.py` 校验覆盖情况、PDF 实际文字、Excel 公式缓存与输入变化、金额、来源哈希和版本引用。它验证测试素材自身，不代表实际应用的端到端测试已通过。

## 演示输入与期望答案

上传给产品演示的素材只从 `inputs/` 选择：

- `inputs/BAG-2026-DE-001/` 是主线，包含询盘邮件、无尺寸背包示意图、工厂 A XLSX、工厂 B PDF、彩盒变更、供应商成本补价、两封客户回复、模拟内部报价审批、工厂交期/MOQ 未确认邮件，以及匹配和冲突 PO。
- `inputs/BAG-2026-DE-002/` 是缺项报价案例：价格范围、MOQ、交期或到港目标缺失时应显式保留 Unknown。
- `inputs/BAG-2026-DE-003/` 是独立 Case：数量低于供应商 MOQ，且供应商未报价，用于 Case 隔离和缺价检查。
- `inputs/adversarial/prompt-injection.eml` 是独立恶意附件。其文字只作为不可信来源内容，不授权发送、审批或放行。

`cases/`、`expected/`、`scenarios/` 和 `scripts/` 是 oracle、评测定义和校验工具，不要上传为业务来源。`cases/*.json` 中的 Sources 记录包含输入文件的 SHA-256、来源角色和邮件摘录、PDF 页码、XLSX 工作表/单元格或图像区域定位。事实断言和按 scope 生效的 resolutions 分开。金额用十进制字符串，Unknown 采用显式 `kind: unknown`。阶段版本是不可变快照；变更版本保留 base version、依赖、diff、审批范围与版本哈希。

## 6–8 分钟演示顺序

1. **0:00–0:45 | 建 Case**：打开 `BAG-2026-DE-001`，上传询盘、背包示意图和两家工厂报价。说明所有输入均为模拟。
2. **0:45–1:45 | 需求与缺项**：提取 3,000 件、FOB Ningbo、Incoterms 2020 和“尽可能 45 天到汉堡”的客户目标。保留目标为请求，不把它显示为到港承诺。由图片识别可见结构，但尺寸、材料等级保持 Unknown。
3. **1:45–2:45 | 基础报价**：对照供应商报价，显示 A 的 CNY 44 + 2 + 4 = 50、28 天估算，B 的 CNY 46 + 2 + 4 = 52、23 天估算。用 7.20 CNY/USD、20% 目标毛利率，复算 A 为 USD 8.69/件、总额 USD 26,070，B 为 USD 9.03/件、总额 USD 27,090。交期均为来源中的估算，不是保证。
4. **2:45–4:10 | 客户变更与多文件 diff**：上传 `change-color-box.eml`，将包装改为定制彩盒提案。之后导入供应商补价邮件，成本项从 CNY 2 改为 5，其他已有成本不变，A 成本变为 CNY 53、报价 USD 9.21/件、差额 USD 0.52/件。展示 Spec、Cost Sheet、Quotation 和供应商确认草稿的新版本与字段级 diff，确认 V1 仍可追溯。
5. **4:10–5:10 | 审批范围**：先看客户条件式回复：60 mm LOGO 和样品审查条件没有变成规格批准。再看无条件邮件，它只确认商业条款，不代表样品批准。内部 V2 报价审批只覆盖商业价格评审。新彩盒 MOQ 和新生产排期仍待工厂确认，因此 V2 报价发布门禁仍阻断。
6. **5:10–6:25 | PO 与生产资料包**：正确 PO 的数量、价格、总额和 FOB Ningbo 与 V2 商业条件相符；允许准备 PI/生产包草稿。生产放行仍因缺少实物样品批准和生产负责人确认而阻断。随后打开冲突 PO，展示 3,200 件、FOB Shanghai 等差异。
7. **6:25–7:15 | 安全与隔离**：展示恶意附件中的外发指令被视为不可信数据；无真实邮件连接时不得显示“已发送”，`sent_at` 必须为 null。尝试从 Case 002 读取 Case 001 Source，应返回 403/404 且不泄露内容。

## 报价 oracle

按单件报价先向上舍入到美分，再乘数量：

`quote_usd_per_piece = ceil_cent((cost_cny_per_piece / 7.20) / (1 - 0.20))`

| 阶段 | CNY/件 | USD/件 | 3,000 件总额 |
| --- | ---: | ---: | ---: |
| A 普通纸盒 V1 | 50.00 | 8.69 | 26,070.00 |
| B 供应商比较 | 52.00 | 9.03 | 27,090.00 |
| A 定制彩盒 V2 | 53.00 | 9.21 | 27,630.00 |

这组数字只验证 PRD 的模拟定价公式。分摊费用是演示估值，不构成通用 FOB 成本模型。彩盒成本补价邮件只确认价格；不确认彩盒 MOQ、样品、生产交期或 45 天到港可行性。

## 评测与重建

`scenarios/demo-scenarios.json` 有 25 条可机读正反向场景。PRD 的 E01–E07、N01–N07 编号保持原样；额外场景使用 X01–X11。Quality Evaluation 文档的编号与 PRD 编号分属不同命名空间，场景中用 `maps_to` 标明对应关系。

生成、重建 oracle 并检查素材：

```powershell
$py = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$node = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
& $py test/scripts/generate_inputs.py
New-Item -ItemType Junction -Path test/node_modules -Target 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules' | Out-Null
& $node test/scripts/build_factory_a_quote.mjs
Remove-Item -LiteralPath test/node_modules -Force
& $py test/scripts/finalize_oracle.py
& $py test/scripts/validate_fixtures.py
```

XLSX 生成器使用 `@oai/artifact-tool`，在 Codex 依赖环境中运行时需让 Node 从该依赖目录解析模块；当前工作副本已生成可上传 XLSX。`validate_fixtures.py` 只读检查来源文件 SHA-256、原生定位、XLSX 实际值/公式缓存、Decimal 报价与总额、版本/依赖图、审批的版本哈希、放行门禁和 25 条场景数量。渲染预览与检查记录在 `.qa/`，不上传。

`expected/quote-golden.json` 是可机读的定价 oracle 摘要；完整事实、阶段快照、审批和放行 oracle 仍以各 `cases/*.json` 的 `expected` 字段为准。两者都不是上传来源。
