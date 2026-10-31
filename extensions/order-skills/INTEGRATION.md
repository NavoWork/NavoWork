# 宿主接入契约与验收边界

初次开发基线 `4e34ce0958912fc3326358589a520cbf38c5103e` 无已提交 agent-kit 合同，因此保留模块内通用端口；后续已针对已提交 `d23ab0a9ecba4dffd4ce0aa97bd496bf668aa156` 增加真实绑定。能力名仍为本模块声明的符号，由真实注册层映射到主模块工具目录；未修改共享 contracts 或真实注册表。

`order_skills.adapter.run(operation, request, context, host, create_file=False)` 直接接收**宿主原生 ExecutionContext**。`HostBindings[ExecutionContext, FileRef, Citation, ToolResult]` 的类型参数是宿主类型占位，未定义同名 DTO。宿主实现的所有 Citation、FileRef 和 ToolResult 原样返回；模块不序列化/重建它们。

| 端口 | 宿主责任 |
| --- | --- |
| `authorize(context, operation, case_id, draft=...) -> bool` | 验证已登录主体、Case 可见性和可读/草稿写入权限；不可从 request 自赋权限。拒绝后不读取能力或引用 |
| `capabilities(context) -> set[str]` | 由实际注册表/执行环境提供能力；模型/request 不能伪造可用能力 |
| `validate_references(context, request)` | 加载并核对所有引用的来源、原文与定位、角色、样品与规格、报价版本/哈希、客户接受范围、撤销/过期与当前 Case；发现越权抛 PermissionError，过期抛 StaleVersion，不可只信输入字符串 |
| `citation(context, evidence) -> Citation` | 将已核验来源定位转成主模块通用 Citation，保留原文及 FileRef 关联 |
| `create_document_draft(context, operation=..., data=..., citations=...) -> list[FileRef]` | 调已有通用文件工具，将模块 data 制作为带草稿标签/缺项/差异/执行前提的文档；Case/运行/generation 来自 ExecutionContext、幂等键来自 ToolCall、业务版本来自宿主；不发布、不批准、不外发。FileRef 由宿主生成 |
| `result(context, status=..., data=..., citations=..., files=..., blockers=...) -> ToolResult` | 用主模块已有工厂组装 ToolResult；run/trace/幂等/警告等宿主字段在此处理，模块不补造 |

宿主可按其现有方法名称写轻量 wrapper。禁止用适配端口替换主模块数据模型。独立领域函数不依赖 Worker、数据库或 Agent Runtime；已有真实合同的映射如下。

调用顺序固定为授权 → 能力检查 → 来源/版本验证 → 确定性分析 → 创建宿主 Citation → 可选通用文件草稿 → 宿主 ToolResult。原始文件解析由宿主先做，领域函数只消费结构化候选；没有 parser 时不能宣称完成原始文件抽取。任何 source 中的提示均不执行。

| 条件 | 返回 |
| --- | --- |
| 缺 case.read / sources.read / artifacts.read_version | blocked + TOOL_UNAVAILABLE，列缺少能力，无引用读取 |
| 生成文件缺 artifacts.create_draft / files.create_document_draft | blocked + TOOL_UNAVAILABLE，不假造文件 |
| Case/来源越权 | blocked + SCOPE_DENIED，data/引用/文件全部清空，不泄露请求 |
| 版本已变更/撤销 | conflict + STALE_VERSION，不调用写入 |
| 文件工具不支持/失败/无 FileRef | blocked + HOST_TOOL_BLOCKED，保留可复核结构化 data，files 为空 |
| 缺字段/定位 | needs_info；未知保留，不能变成零 |
| 商务/样品冲突或 PI 草稿 | needs_review；PI 仍是草稿，执行前提独立 |
| 完整匹配的分析 | success 只代表该分析完成；不代表批准、签约、到账或生产放行 |

`HostBlocked` 是可报告的工具/策略阻断；未预期宿主异常向上抛给主模块错误处理，不吞异常后假报成功。宿主文件写入必须提供自身事务/幂等保障；本模块不创建第二套幂等存储或批准服务。通用端口测试中的 FakeHost 只演示调用顺序、拒绝/冲突与原生类型透传；新增的真实合同兼容测试加载已提交的真实类和 ToolService，但宿主 Port 仍为内存替身，**不证明真实 ACL、数据库版本并发或持久化幂等已接入**。

## 已提交 d23ab0a 的具体绑定

`order_skills.agentkit.AgentKitBindings` 直接导入真实合同与 CaseContextPort/FileStorePort/ArtifactPort，不定义替代 DTO。`call_order_tool(binding)` 是可注册入口函数，不创建第二个 ToolService、工具注册表、Worker 或 Agent Runtime。宿主为每个真实 ToolCall 创建一个绑定：

```python
from order_skills.agentkit import AgentKitBindings, call_order_tool

bindings = AgentKitBindings(
    tool_call,  # 主模块真实 ToolCall，name 为 sample_feedback/po_check/pi_prepare
    case=case_port, files=file_port, artifacts=artifact_port, tools=tool_service,
    domain_policy=host_order_binding_policy,
)
result = call_order_tool(bindings)  # 真实 navowork_agent.contracts.ToolResult
```

ToolCall.arguments 精确包含 `{request: 领域输入, create_file?: bool}`，额外 context/权限/shell 等字段拒绝。上下文只从注入 CaseContextPort.context() 获取；执行 Case/Job/Run/generation/read/write 约束及 assert_current。d23ab0a 的 LocalAdapter.assert_current 在只读场景也检查 can_write，因此它可能阻断 can_write=false 的分析；模块遵从宿主拒绝，不跳过 fence。后端 CaseContextPort 可在保持授权和 generation 检查的前提下支持合法只读分析，此语义由主模块负责。

生产 evidence 必须使用已授权不透明 file_id（领域字段名 source_id）、捕获时 sha256 和解析器原生 locator 字典；CLI 字符串定位只用于早期离线输入，不会被强行转换成伪造字典。用 FileStorePort.list_files 核验 Case/哈希，并通过**真实 ToolService.call(ToolCall(name="read_document", arguments={"file_id": ...}, ...))** 获取宿主解析结果，逐一校验定位和原文摘录，再创建 Citation(file_id,sha256,locator,excerpt)。所有源文件读取都经宿主，不接受源路径，不自行读磁盘/PDF/邮件。

除字节/定位之外，宿主必须注入 `domain_policy(context, request, artifact_port)` 核验候选值/分类与原文关系、来源业务角色、样品/批准范围、报价/规格版本与撤销/接受状态。它是宿主代码，不能从工具参数传入；缺失时 blocked。模块不会根据文件名、quote 中的文字或 FileRef.role=source 就认定是客户批准。业务版本由 ArtifactPort 和现有批准服务验证，不把 generation 当作规格/报价版本。

ToolResult 顶层只写 status/outputs/artifacts/data/warnings/questions/retryable/code。Citation JSON、阻断详情和适配元信息放 `data.order_skills`；缺项生成原生 Question，文件使用 outputs，保留宿主原生 ArtifactRef、warnings/questions/retryable/code。不得向真实 ToolResult 增加顶层 files/citations/blockers。

d23ab0a 的 registry 只有特定 quotation 发布/导出与已有文件编辑，没有样品报告、PO 报告或 PI 的通用新文档草稿工具。默认 create_file=True 因缺工具明确 blocked；不会用 publish_documents 的报价文件冒充 PI。待主模块注册相应**草稿工具**后，可由宿主构造绑定时配置 draft_tool 和 draft_arguments 映射。文件写入只调用既有 ToolService.call，幂等键由原 ToolCall 派生并传回宿主；execute_once/ArtifactTransaction 原子写入、业务 CAS 和 EventSink 审计仍由主模块工具/执行层统一持有。本模块不直接 put_file/append_artifact、操作事务或发审计事件，避免第二套存储与重复事件。

兼容测试从固定 Git object 通过只读 git show 在内存导入实际 contracts/ports/ToolService；不读取 justike 工作区、不复制未提交内容、不合并 d23ab0a。新增目录中的测试宿主仅模拟端口；可选已注册文件工具测试也是明确的替身，不宣称真实渲染或事务成功。

主模块接入验收仍需完成：

1. 注册 manifest 三个资源和 operation 到主 Agent/Worker，注入真实端口、ToolService 与 domain_policy；真实合同映射已提供。
2. 用真实工具加载并解析来源，核验 Case/版本/角色/逐字定位，并校验候选输入 schema；模型抽取结果经过领域检查。
3. 用通用文件工具生成样品反馈报告、PO 核对报告和 PI 草稿；返回真实 FileRef，并完成宿主要求的格式/视觉检查。
4. 真实执行跨 Case 拒绝、过期版本冲突、无工具 blocked、幂等草稿写入和不可越权批准/外发；单独验收文件工具部分失败后的重试。
5. 保留早期素材缺项；只在明确选择后续 core15 快照时加载后续确认，不能用未来证据消除早期阻断。
