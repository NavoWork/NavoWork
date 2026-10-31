# W2 独立能力交付记录

当前增量：已针对主模块稳定提交 `d23ab0a9ecba4dffd4ce0aa97bd496bf668aa156` 完成真实合同绑定及兼容测试。完整回归 **73 项全部通过，0 skipped**；其中新增 20 项为 pinned 合同/ToolService 兼容性测试。初次交付记录保留在下方，协议补充见文末。

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

## d23ab0a 稳定协议兼容增量

增量基于本分支首个提交 `a81e35254c0553813c886b8c3c4d4d086dea7653`，仍只修改 `extensions/order-skills/`。未合并 d23ab0a：用只读 Git object 获取其已提交内容，未读取/复制主线未提交实现，未操作共享 checkout 的分支或暂存区。

新增 `order_skills/agentkit.py` 直接导入已提交的真实 ExecutionContext/FileRef/Citation/ToolCall/ToolResult/Question，并通过 CaseContextPort、FileStorePort、ArtifactPort 与既有 ToolService 绑定。引用使用原生 locator 字典及捕获时 sha256，来源只接受宿主列出的 file_id，读取调用真实 read_document 工具。域值/来源业务角色/批准范围及当前版本须由宿主注入 domain_policy 核验，缺 policy blocked。Case/read/write/generation 由宿主上下文与 assert_current 控制；工具参数不可提供 context/权限。

结果符合真实 ToolResult 的 extra=forbid 合同：文件在 outputs，引用与阻断详情在 data.order_skills；保留原生 artifacts/warnings/questions/retryable/code。ToolCall 提供幂等键，未向 ExecutionContext 添加字段。条件性反馈、草稿语义和早期缺证场景保持原有行为。

`tests/committed_agentkit.py` 在测试进程内用 git show 读取 pinned revision 的实际模块代码，测试不落盘复制来源，也不把 schema/DTO 手写一份代替合同。实际导入并运行了 d23ab0a 的 ToolService.call 与四个 Port 的协议检查。业务宿主是显式内存替身；新增可选草稿工具的两个测试也只是注册替身，不是真实渲染、数据库事务或生产 ACL 测试。

实际运行：

```powershell
# 工作目录：C:\Users\Justike\.codex\worktrees\b981\NavoWork\extensions\order-skills
& $orderPy -m unittest discover -s tests -p test_agentkit_compat.py -v
& $orderPy tools/verify.py --qa-deps .qa/deps --require-qa
```

最终完整输出：`Ran 73 tests in 2.291s` / `OK`，无 skipped。原生三类 result.data 也已用发布的 output schema 校验；PI 元信息不会导致 additionalProperties 冲突。新增验证覆盖真实模型额外字段拒绝、dict locator/引用往返、真实 ToolService 按 ID 读取、缺文件工具 blocked、缺策略 blocked、权限/Case/generation/来源哈希/业务版本冲突、定位/摘录不匹配拒绝、原生 Question、拒绝权限/shell 注入，以及可选已注册工具替身的原生输出和部分完成信息透传。

待主模块接入项仍独立：注册三个扩展操作与 Skills、注入真实业务 policy 与 backend ports、实现/注册通用文档草稿工具并验证 ArtifactTransaction/幂等/CAS、Worker/workbench 接入、真实模型运行和文件视觉检查。d23ab0a 当前没有本任务所需通用新文档草稿工具，实际 create_file=True 明确 TOOL_UNAVAILABLE/blocked，不使用报价生成器冒充 PI。LocalAdapter.assert_current 的只读/写权限语义限制已写入 INTEGRATION，模块不绕过宿主 fence。
