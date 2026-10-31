# W2 样品与订单 Skills

三个**产品内** Skill、标准库领域函数、离线 JSON CLI 和宿主薄适配层。入口清单为 `manifest.json`，`order_skills/agentkit.py` 绑定已提交 `d23ab0a` 通用合同。模块不安装个人 Codex Skills，不提供文档编辑器、Agent Runtime、报价计算器或批准服务；最终文件通过宿主已有通用文件工具制作。

| 资源 / operation | 独立函数 | 输出重点 |
| --- | --- | --- |
| `skills/sample-feedback/` / `sample_feedback` | `review_sample(request)` | 样品/规格绑定、四种回复、带证据修改清单、未关闭条件 |
| `skills/po-check/` / `po_check` | `compare_po(request)` | 基准版本/状态、客户接受证据状态、字段差异、买方原文与定位 |
| `skills/pi-prepare/` / `pi_prepare` | `prepare_pi(request)` | PI 草稿结构、PO 复核、待确认清单、独立执行前提 |

每个目录含 `SKILL.md`、自包含 Draft 2020-12 `input.schema.json` 和 `output.schema.json`。输出 schema 描述领域 data，**不是新的 ToolResult 合同**。领域函数只返回结构化分析；宿主适配层使用宿主工厂创建 ToolResult，模块字段全部放在 data。

## 实际运行

以下命令在仓库根目录执行，不更改根配置、依赖或共享测试素材。标准库领域测试和 CLI 无需安装。Python 3.12+；本机实际使用 bundled Python 3.12.14。

```powershell
$orderPy = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
Push-Location extensions/order-skills
& $orderPy -m unittest discover -s tests -p test_domain.py -v
& $orderPy -m order_skills sample_feedback examples/sample-conditional.json
& $orderPy -m order_skills po_check examples/po-port-conflict.json
& $orderPy -m order_skills po_check examples/po-missing-acceptance.json
& $orderPy -m order_skills pi_prepare examples/pi-without-approved-sample.json
Pop-Location
```

CLI 也接受 `-` 从 stdin 读取 JSON。输出 `mode=offline_deterministic`；正常完成分析（即使有缺项/冲突）退出 0，输入错误退出 2。CLI 不执行宿主授权、模型、文件生成或批准，不能用于宣称业务 Gate 通过。`examples/` 全为显式 synthetic 示例，不是真实报价/客户接受记录，不从 oracle 伪造来源。

可选 QA 依赖用于 Schema 验证（jsonschema）和已有 PDF 原文回放（pypdf）；真实合同兼容测试使用宿主的 Pydantic/文件工具依赖，并只读加载 pinned Git revision 中的实际 contracts/ports/ToolService，不合并主线或读取未提交代码。缺可选库会显式 skip；本次完整验证记录见 `DELIVERY.md`。可在独立目录安装，避免修改宿主依赖：

```powershell
Push-Location extensions/order-skills
& $orderPy -m pip install --target .qa/deps -r requirements-qa.txt
& $orderPy tools/verify.py --qa-deps .qa/deps --require-qa
Pop-Location
```

`tools/build_resources.py` 可重新生成 schemas 和 synthetic examples，只写本模块目录。

## 输入与检查边界

货币/数量用十进制字符串，最多 12 位整数和 6 位小数，不接受浮点、科学记数法、NaN、Infinity 或负数；数量须正数。只核对已有单价和行金额的精确乘积、合计，不设汇率、利润或额外定价策略。复杂税费、折扣、计价单位转换等必须由宿主其他工具先形成明确比较口径，本输入不支持的字段报错，不静默丢弃。

PO 与基准均为 document：header 字段为 `{value, raw, evidence}` 或 null；lines 需要稳定 `line_id`，含 sku/quantity/unit/unit_price/amount。所有字段都保留原文/证据。原件未显式给出规格版本、付款或卖方时保留 null，不以领域常识填补。大小写/空白可归一；语义同义、箱件转换、模糊行映射须人工/其他工具核验，可能得到保守的复核提示。

evidence 为候选来源定位（case_id/source_id/locator/quote/role），由宿主解析为通用 Citation。生产 Agent Kit 绑定还必须提供捕获时 sha256，locator 必须为解析器返回的字典（CLI 兼容早期字符串示例）。引用经真实 `ToolService.call(read_document)` 核对 FileRef 哈希、位置和逐字摘录；source_id 是已授权 file_id，不接受源文件路径。声明 scope 和 version_id 并不能赋予批准；完整语义抽取及来源业务角色/版本/撤销状态真实性依赖宿主注入 policy，缺 policy 明确 blocked。

样品 `full/partial/conditional/rejected` 与宿主批准记录分离；条件未关闭、错误范围/版本/样品、缺定位、修改要求均不能支持完整批准。商业接受不代表实物样批准。PI 即使样品未批准仍可形成草稿，必须展示 pending prerequisites；草稿不声称已签署、收到款项或放行。

## 宿主接入

参见 `INTEGRATION.md` 的已提交协议补充。通用 `HostBindings` 保留为本地端口；新增 `AgentKitBindings` 直接导入主模块真实 ExecutionContext、FileRef、Citation、ToolCall、ToolResult 和 Question，不创建同名合同。真实 ToolResult 仅使用允许的顶层字段：文件放 outputs，模块引用/阻断详情放 data.order_skills，缺项使用原生 questions。兼容测试中合同/ToolService 是 pinned Git 原代码；宿主 Port 仍为显式测试替身，不代表真实后端集成。

独立能力验收与主链路验收分开。资源真实注册、Worker 调用、真实文件工具、审批服务和视觉检查由现有“实现 Agent 文件工具闭环”工作统一接入。本模块完成不能等同于生产主链路已接入。
