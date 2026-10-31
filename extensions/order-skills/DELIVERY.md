# W2 独立能力交付记录

日期：2026-10-31（Asia/Shanghai）。共同基线核验为 `4e34ce0958912fc3326358589a520cbf38c5103e`，提交信息为合入 `origin/lirui` 的合并提交。开发分支 `codex/order-skills`，managed worktree：`C:\Users\Justike\.codex\worktrees\b981\NavoWork`。本交付只包含 `extensions/order-skills/`；未修改共享 checkout、backend、fontend、contracts、根配置或 test，也未复制未提交 agent-kit。

三个产品内 Skill、输入/输出 JSON Schema、领域检查函数、JSON CLI、宿主薄适配层、synthetic examples 和离线测试已完成。资源入口 `manifest.json`，使用命令见 README，接入端口及主链路待办见 INTEGRATION。

## 实际验证结果

Python 3.12.14；原始 PDF 只读回放使用 bundled pypdf 6.10.0。JSON Schema 验证库 jsonschema 4.25.1 隔离安装在忽略目录 `.qa/deps`，不修改系统或共享项目依赖。首次标准库运行因缺该库跳过一项，安装后完整运行 **53 项测试全部通过，0 skipped**。

完整测试实际命令（在本模块目录）：

```powershell
$orderPy = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $orderPy tools/verify.py --qa-deps .qa/deps --require-qa
```

本机从 PyPI 下载 QA 包需沙箱网络提升；下载目录在普通沙箱中不可读，完整 Schema 验证用提升权限只读访问该本地依赖目录。标准库领域函数/CLI 不依赖该权限或验证库。

| 验证类别 | 实际结果与限制 |
| --- | --- |
| 确定性领域检查 | 样品四类回复、条件不能升级批准、范围/样品/规格/角色/定位约束、带证据修改清单；PO 数量/价格/金额/币种/术语/港口/付款/规格差异、精确小数合计、混合单位阻断、缺证基准、不可变版本 ID；PI 无样品批准仍可草稿、执行前提独立。通过 |
| 宿主接口替身 | FakeExecutionContext/FakeCitation/FakeFileRef/FakeToolResult 类型透传；授权先行、各缺工具 blocked、越权 redaction、过期版本 conflict、文件工具失败、宿主自持幂等示例。通过。不是实际合同兼容或真实 ACL/持久化测试 |
| Schema | 六份 Draft 2020-12 schema 合法，三类示例输入/实际输出通过；PI output schema 拒绝 payment_received=true。通过 |
| 早期原始来源只读回放 | 条件客户回复未批准；商业接受邮件未批准样品；真实 po-conflict.pdf 的 FOB Shanghai 原文匹配并保留 page:1/Trade term 定位。通过。字段映射为人工明确投影，不宣称模型抽取 |
| 后续 core15 独立回放 | E04 对 S03/TechPack V3 的样品范围确认可被支持；仍不表示签约、订金或放行。通过。未将 E04 导入早期测试 |
| 独立 CLI 实际进程 | 四条 `python -m order_skills ...` 命令均成功并输出合法 JSON，关键结果见下方 |
| 真实模型 | 未运行；没有伪造模型评测或抽取准确率 |
| 文件生成/视觉检查 | 未运行；无宿主通用文件工具真实绑定，本任务不创建替代文件生成器 |
| Worker/主链路 | 未接入；由“实现 Agent 文件工具闭环”统一注册和真实验收 |

原始模拟 PO PDF 的 pypdf 读取会输出 `incorrect startxref pointer(1)` / `parsing for Object Streams` 修复提示，但实际原文断言通过。未修改或重建该 PDF；这不是文件视觉检查。

实际 CLI：

```powershell
& $orderPy -m order_skills sample_feedback examples/sample-conditional.json
& $orderPy -m order_skills po_check examples/po-port-conflict.json
& $orderPy -m order_skills po_check examples/po-missing-acceptance.json
& $orderPy -m order_skills pi_prepare examples/pi-without-approved-sample.json
```

对应结果：`response_kind=conditional`、`sample_approval_supported=false`、1 条绑定修改；`po.named_place` 显示 Shanghai/Ningbo 差异及原文/字段定位；基准 `quote-v3 / draft`、客户接受证据 `false / null`；PI `draft`、`signed=false`、`payment_received=false`，样品/商务/签署/订金/供应商排期/内部放行均列为待确认。示例全为 synthetic，不构成商业来源证据。

## 未完成项与依赖

独立能力已完成；主链路接入尚未完成。需主模块冻结/提供通用合同映射、能力注册、原始来源解析与真值核验、真实 Case/版本/批准检查、持久化草稿幂等、文件工具与视觉检查，再连接 Worker。此模块不通过聊天内容创建批准或赋予权限，不能据离线 success 跳过宿主 Gate。

语义理解由产品主 Agent/解析工具提供，确定性函数检查已抽取的结构化候选。保守关键词仅为常见条件/延期措辞兜底，不能保证任意语言或复杂句式的语义分类；付款同义表达、复杂折扣税费/币种/单位转换等按明确比较口径交其他工具/人工复核。

Context7 MCP 入口在本会话工具清单中不可用；已查阅 Python 官方 decimal 和 typing.Protocol 文档作为标准库实现依据：

- https://docs.python.org/3/library/decimal.html
- https://docs.python.org/3/library/typing.html#typing.Protocol

本分支交付后由主协调链自行审查/合入；本任务不合入 justike，不推送或创建 PR。
