# 17｜Coding Agent 分工与交接规范

> 用途：直接作为多个编程 Agent 的协作合同与任务边界。  
> 核心原则：**每个 Agent 修改清晰的目录与接口，不跨域创造自己的一套业务事实。**

## 1. 主仓库结构（推荐）

```text
trade-workbench/
├── apps/web/
│   ├── app/
│   ├── components/{workspace,editors,agent,review,delivery}/
│   └── lib/api/
├── services/api/
│   ├── app/api/
│   ├── app/domain/{cases,facts,costing,quotation,validation}/
│   ├── app/artifacts/{schemas,patching,versioning,dependency,renderers}/
│   ├── app/ingestion/{email,excel,pdf,image}/
│   ├── app/agent/{graph,tools,model_gateway}/
│   ├── app/workflows/
│   └── tests/
├── contracts/{pydantic,openapi,examples}/
├── fixtures/cases/BAG-DE-001/
├── infra/
├── docs/technical-design/
└── README.md
```

## 2. Agent A：架构 / Runtime

**文件所有权**：`services/api/app/agent/`、Job/Run 服务、SSE 后端部分。  
**任务**：实现单主 Agent、Tool Adapter、Run 状态转换、持久 Checkpointer、中断恢复、事件生成、有限重试。  
**输入合同**：`CaseContext`, `ToolCallRequest`, `ToolResult`, `ApprovalRef`。  
**输出合同**：`RunSnapshot`, `JobEvent`, `ArtifactVersionRef`。  
**绝不做**：自己直接更新订单金额/审批状态；对外发送未经授权邮件。  
**验收**：同一个 Run 在缺彩盒新报价时暂停、补资料后恢复；重启不重复创建版本。

## 3. Agent B：Domain / Artifact Engine

**文件所有权**：`app/domain/`、`app/artifacts/`、数据库 migration、导出器。  
**任务**：模型、FactResolution、Artifact Canonical Schema、Patch/Diff、版本、依赖、Costing/Quotation/PI/生产 Gate。  
**输入合同**：`TypedArtifact`, `VersionedPatch`, `PricingPolicy`, `FactResolutionRef`。  
**输出合同**：`ArtifactVersion`, `ValidationReport`, `ImpactReport`, `RenderedFileRef`。  
**绝不做**：在领域函数里调用大模型推断缺失成本；把发布状态放进前端 localStorage。  
**验收**：金额计算全通过、旧版不可改、409 冲突、无审批不能发布。

## 4. Agent C：Workbench Frontend

**文件所有权**：`apps/web/`。  
**任务**：三栏工作区、Source/Artifact Tree、AG Grid、Active Context、Agent Timeline、Diff、Approval、导出。  
**输入合同**：服务端 OpenAPI TypeScript Client、SSE JobEvent。  
**输出合同**：`DraftPatchRequest`, `ReviewAction`, `JobStartRequest`。  
**绝不做**：在浏览器模拟审批结果、用前端 JS Float 计算正式金额、把 `applied_to_draft` 显示为 `released`。  
**验收**：人工选择成本字段发任务；Agent 修改预览可见；断网恢复；409 不丢用户编辑。

## 5. Agent D：Ingestion / QA / Fixtures

**文件所有权**：`app/ingestion/`、`fixtures/`、`tests/e2e/`、评测脚本。  
**任务**：EML/Excel/PDF/图像解析、Span/Locator、原始供应商表格归一化、Golden Dataset、恶意样本、测评报告。  
**输入合同**：`SourceId`, `ParseConfig`。  
**输出合同**：`SourceSpan`, `FactAssertionCandidate`, `ParseReport`。  
**绝不做**：模型认出“看起来像防水面料”就填正式材料等级；为了通过测试在业务代码硬编码 BAG-DE-001。

## 6. 所有 Coding Agent 的共同提示词（模板）

```text
你在 TradeWorkbench Monorepo 上工作。产品是 B2B 箱包 OEM/ODM 的 AI-Native
跟单执行工作台，不是 CRM/ERP。系统以 Job + Artifact 为中心，Case 为隔离上下文。

先读：docs/technical-design/README.md，以及与你任务相关的技术 MD。
必须遵守：Source 不可变；FactAssertion 不直接成为业务已批准事实；
ArtifactVersion 不可原地覆盖；用户接受 Patch 不等于报价/生产批准；
金额由 Decimal 确定性工具计算；Agent 不得越权发邮件或自行批准。

你的任务：<在此填写 PR 编号、目录范围、输入输出合同、验收测试>。

请先确认现有 Repo 的 DTO / API / 测试，不要新增重复字段或另起架构。
若合同缺失，请先补最小接口提案并标记 blocker，不要臆造已确认业务事实。
修改代码后运行本模块测试与跨模块契约测试，给出文件变化、测试结果、
风险与未完事项。不要声称没有实际执行的工具/测试已成功。
```

## 7. PR 交接模板

每个 PR 描述必须有：

```markdown
### Scope
本 PR 做什么 / 明确不做什么

### Contract changes
新增/修改哪些字段、API、Tool、Event；是否向后兼容

### Artifacts
产生哪些可验证的工件版本或文件

### Tests run
实际执行的测试命令与结果；失败项

### Demo evidence
如何用 fixture 或 curl 复现（不是仅提供 UI 截图）

### Risks / Blockers
未验证的假设、依赖其他 PR 的事项
```

## 8. 联调协议

1. `PR-00` 冻结 Domain / API / Tool Names，初始 Mock JSON 与正式响应具有同样结构。
2. Agent B 提供确定性 Costing Tool，Agent A 通过 Tool Adapter 调用；不能复制一份新算法。
3. Agent D 为真实格式 Fixture 生成 Expected Labels；不能由 Agent A 直接看到答案来“规划”。
4. Agent C 读取 SSE Event，不根据随机生成的聊天文字判定 Tool 状态。
5. 所有模块完成后先跑 `Flow A`，再 `Flow B`，最后 `Flow C`；遇到失败按 Domain/Runtime/UI 三层定位，而不是整体重写。

## 9. 交付优先级（相同时间冲突时）

`业务正确性与越权防护 > Artifact 版本/文件可靠性 > 可恢复执行 > 来源追溯 > UI 动画与美观 > 新增 SOP 数量`。

如果无法做到所有功能，请明确缺失能力，并保证已经交付的工作流能真实运行。
