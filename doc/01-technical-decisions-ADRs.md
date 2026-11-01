# 01｜技术决策记录（Architecture Decision Records）

> 用途：Coding Agent 不得绕过已定工程边界；对“推荐未拍板”的项允许局部替换，但必须记录取舍。  
> 状态标签：**已定（产品约束） / 建议（待实施验证） / 待决策**。

## ADR-001：单体应用 + Worker，暂不微服务

- **状态**：建议。
- **决定**：一套 `web`、一套 `api`、一套 `worker`，一个 PostgreSQL 实例及 S3/MinIO 对象存储。
- **原因**：三条核心工作流需要跨领域事务一致性；团队时间有限。
- **不采用**：将解析、报价、文件、审批、Agent 拆成独立服务。
- **触发重评**：多团队独立发布、解析负载明显与业务 API 不同、需要独立隔离执行。

## ADR-002：Canonical Artifact 是业务真实表示，XLSX/PDF 是渲染输出

- **状态**：已定（产品/工程核心原则）。
- **决定**：结构化 JSON（Pydantic 校验）保存规格、BOM、Cost Sheet、Quotation、PI、生产指令；编辑器和导出器是其投影。
- **好处**：Field Path 稳定；可复算、可 Diff、可被 Agent/人共同编辑。
- **代价**：不能承诺无损编辑所有外部复杂 Excel；需要维护模板映射。
- **触发重评**：真实客户要求以任意原始 Excel 为唯一编辑源时，可用混合模式（内部生成结构化文件、外部复杂文件作为 opaque asset）。

## ADR-003：业务规则由后端确定性 Tool 执行

- **状态**：已定。
- **决定**：金额使用 `Decimal`，费用与币种归一，价格和 PO/PI 校验独立于 LLM。
- **反例**：Prompt 中说“请你精确计算价格”，然后把模型文字当正式报价。
- **边界**：模型可以发现表格语义、提出规则假设，规则生效需领域配置/人工核准。

## ADR-004：Fact Assertion 与业务采用（Resolution）分离

- **状态**：已定。
- **决定**：邮件或文件原文保存不可变声明，单独记录对某业务用途采用了哪一条以及审批证据。
- **原因**：客户最新请求 ≠ 内部已批准更改 ≠ 供应商已经接受变更。
- **触发重评**：不会取消此分离，只会增加更多事实范围（如分 SKU/批次）。

## ADR-005：单主 Agent + Typed Tools

- **状态**：建议。
- **决定**：一个 Agent 负责执行计划；File/Domain/Artifact/Gate Tools 显式暴露；不做七个角色模拟群聊。
- **取舍**：降低调试复杂度，任务职责通过 Tool/Graph 明确；长期可把复杂 QC 子流程抽成 Subgraph。
- **替代**：在 Hackathon 时间非常紧时自建固定 Workflow State Machine，但仍保留 Tool Contract。

## ADR-006：LangGraph 持久化只管理 Run，不作为业务数据库

- **状态**：建议。
- **决定**：Graph State 只存 ID 与运行阶段，业务状态在 PostgreSQL 域表；持久 Checkpointer 用独立 schema。
- **重要限制**：`interrupt()` 恢复时节点前序代码可能重跑，所有有副作用的 Tool 使用 Idempotency Key 并尽可能将审批点置于副作用之前。
- **参考**：https://docs.langchain.com/oss/python/langgraph/interrupts

## ADR-007：AG Grid Community 只承担网格编辑

- **状态**：建议。
- **决定**：采用自定义业务字段列编辑，计算由后端、XLSX 由 openpyxl 输出。
- **警告**：不要设计依赖 AG Grid Enterprise 原生 Excel Export、完整公式或高级范围选取的 P0 需求。
- **参考**：https://github.com/ag-grid/ag-grid 、https://www.ag-grid.com/javascript-data-grid/excel-export/

## ADR-008：仅用可逆草稿自动执行，正式业务动作有独立 Gate

- **状态**：已定。
- **决定**：报价发布、客户规格采纳、生产放行、对外发送是四种独立授权；用户“接受 Patch”只等于写入草稿。
- **错误示例**：`approved=true` 同时代表以上四个完全不同的审批。
- **目标**：高风险越权操作数 = 0。

## ADR-009：文件输入先有证据锚点，后有 LLM 结构化结果

- **状态**：已定。
- **决定**：文件字节 → Parser Span → 候选断言（含 `source_locator`）→ 人确认/规则校验。
- **说明**：Structured Outputs 只保证返回符合 Schema，**不保证抽取值真实**；不能以模型置信度代替证据核验。
- **参考**：https://developers.openai.com/api/docs/guides/structured-outputs

## ADR-010：采用可乐观并发的 Copy-on-Write 版本

- **状态**：建议。
- **决定**：ArtifactVersion 内容不可变；编辑基于 `base_version_id`，写入在事务内检查与原版本一致，冲突返回 `409`。
- **不采用**：多用户 CRDT 协作、直接覆盖已批准 XLSX 文件。
- **触发重评**：出现多人实时编辑与频繁冲突时再引入 CRDT/OT。

## ADR-011：外部集成后置，P0 仅真实导出与邮件草稿

- **状态**：已定（MVP 边界）。
- **决定**：P0 不依赖 Gmail/Outlook/ERP 登录；允许以真实 Source 文件上传、导出 ZIP、生成邮件草稿展示流程。
- **约束**：UI 状态显式标为 `prepared / exported`，不得显示为 `sent`。

## ADR-012：自定义本体极简化

- **状态**：建议。
- **决定**：本期只实现 `Case, Source, FactAssertion, FactResolution, Job, Run, Artifact, ArtifactVersion, ChangeSet, Approval, Delivery`，不引入图数据库、通用动态 Schema 平台或全公司知识图谱。
- **预留**：所有实体 ID 稳定、Case Scope 明确，后续可扩展到多品类/多公司。

## ADR-013：可观测性贯穿 Tool 和业务事务

- **状态**：建议。
- **决定**：以 `trace_id + run_id + case_id + tool_call_id` 关联事件、错误和修改；源文件内容、令牌、银行数据不默认进入日志。
- **目的**：能解释每份交付物为什么产生、由谁批准、哪次执行改变了它。

## 需要技术 Spike 的待决策项

| 编号 | 问题 | 默认先用 | 通过/不通过的判断 |
|---|---|---|---|
| S01 | 文字型 PDF 表格可否稳定抽取 | Docling + 针对字段的 parser | 样例报价字段召回满足验收集；错误不可静默通过 |
| S02 | PDF 跨页/坐标定位的可靠性 | `page` + 文本片段，坐标可空 | 点击来源能定位/搜索原文；不假造 bbox |
| S03 | 使用哪个 LLM / VLM | 可配置 Provider Adapter | 真实样例抽取准确率、时延、费用、可调用性 |
| S04 | 异步执行队列选什么 | 单 Worker + Postgres Event | 断线、重启后 Run 可恢复；否则引入 Redis/RQ |
| S05 | 是否引入富文本编辑器 | Tiptap（可延后） | 需要段落内编辑再做；MVP可用结构化表单 |
| S06 | 生成 PDF 的路径 | DOCX 模板 → 受控渲染 | 字体、表格分页、结果一致；不可只看文件生成成功 |

## 决策修改流程

1. 先写最小 Spike（输入数据、预期、结果），不能凭印象替换。
2. 修改 ADR 的状态、日期、替代方案、兼容影响。
3. 如改变 Schema/API/Artifact 语义，必须同步相关文档并新增契约测试。
