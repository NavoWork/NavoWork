# 宿主接入契约与验收边界

基线 `4e34ce0958912fc3326358589a520cbf38c5103e` 无已提交 agent-kit 合同。本文件描述模块内 provisional port，不冻结共享 ABI，不要求修改 contracts。能力名为本模块声明的符号，由真实注册层映射到主模块工具目录。

`order_skills.adapter.run(operation, request, context, host, create_file=False)` 直接接收**宿主原生 ExecutionContext**。`HostBindings[ExecutionContext, FileRef, Citation, ToolResult]` 的类型参数是宿主类型占位，未定义同名 DTO。宿主实现的所有 Citation、FileRef 和 ToolResult 原样返回；模块不序列化/重建它们。

| 端口 | 宿主责任 |
| --- | --- |
| `authorize(context, operation, case_id, draft=...) -> bool` | 验证已登录主体、Case 可见性和可读/草稿写入权限；不可从 request 自赋权限。拒绝后不读取能力或引用 |
| `capabilities(context) -> set[str]` | 由实际注册表/执行环境提供能力；模型/request 不能伪造可用能力 |
| `validate_references(context, request)` | 加载并核对所有引用的来源、原文与定位、角色、样品与规格、报价版本/哈希、客户接受范围、撤销/过期与当前 Case；发现越权抛 PermissionError，过期抛 StaleVersion，不可只信输入字符串 |
| `citation(context, evidence) -> Citation` | 将已核验来源定位转成主模块通用 Citation，保留原文及 FileRef 关联 |
| `create_document_draft(context, operation=..., data=..., citations=...) -> list[FileRef]` | 调已有通用文件工具，将模块 data 制作为带草稿标签/缺项/差异/执行前提的文档；Case/版本/幂等键来自 ExecutionContext；不发布、不批准、不外发。FileRef 由宿主生成 |
| `result(context, status=..., data=..., citations=..., files=..., blockers=...) -> ToolResult` | 用主模块已有工厂组装 ToolResult；run/trace/幂等/警告等宿主字段在此处理，模块不补造 |

宿主可按其现有方法名称写轻量 wrapper。禁止用适配端口替换主模块数据模型。若协议冻结后需要更名/异步包装，在本模块或集成模块做映射，独立领域函数不依赖 Worker、数据库或 Agent Runtime。

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

`HostBlocked` 是可报告的工具/策略阻断；未预期宿主异常向上抛给主模块错误处理，不吞异常后假报成功。宿主文件写入必须提供自身事务/幂等保障；本模块不创建第二套幂等存储或批准服务。离线测试中的 FakeHost 只演示调用顺序、拒绝/冲突与原生类型透传，**不证明真实 ACL、数据库版本并发或持久化幂等已接入**。

主模块接入验收仍需完成：

1. 注册 manifest 三个资源和 operation 到主 Agent/Worker，绑定真实 ExecutionContext 和 ToolResult。
2. 用真实工具加载并解析来源，核验 Case/版本/角色/逐字定位，并校验候选输入 schema；模型抽取结果经过领域检查。
3. 用通用文件工具生成样品反馈报告、PO 核对报告和 PI 草稿；返回真实 FileRef，并完成宿主要求的格式/视觉检查。
4. 真实执行跨 Case 拒绝、过期版本冲突、无工具 blocked、幂等草稿写入和不可越权批准/外发；单独验收文件工具部分失败后的重试。
5. 保留早期素材缺项；只在明确选择后续 core15 快照时加载后续确认，不能用未来证据消除早期阻断。
