# 11｜安全、授权、人工审批与越权防护

> Owner：后端 / Agent / 产品负责人 ｜ P0 强制要求：**重要承诺和外部行为必须由正确的人授权**。

## 1. 威胁模型与边界

Threat Sources：客户邮件、供应商报价、PO、图片、第三方工具返回、恶意附件。  
Protected Assets：客户/供应商资料、商业价格、收款信息、授权决策、已发布订单/规格、外部渠道凭据。

核心边界：**外部资料不等于可执行指令，模型建议不等于授权，用户主动批准草稿不等于客户或工厂确认。**

## 2. 权限分级

| Level | 描述 | 示例 | P0 策略 |
|---|---|---|---|
| L0 | 只读/抽取/计算 | 查询、核对、价格模拟 | 自动，需 Case Scope |
| L1 | 可逆草稿 | Spec/Quotation/PI Draft、RFQ 邮件草稿 | 可以自动执行并留痕 |
| L2 | 内部发布 | 正式报价内部审批、规格采纳、生产资料标为已批准 | 校验业务角色 + 版本 |
| L3 | 对外正式动作 | 发正式报价、承诺交期、采购下单 | P0 不自动执行；P1 单独授权 |
| L4 | 高风险动作 | 改银行账户、付款、放单、实物 QC 最终放行 | P0 不实现自动化 |

## 3. Gate 不应只有一个 `approved=true`

| Gate | 执行者与必要依据 | 后果 |
|---|---|---|
| `DRAFT_APPLY` | 当前 Case 的授权编辑者接受 Patch | 仅创建新版草稿 |
| `QUOTE_RELEASE` | 内部价格负责人 + 对应 Quotation Version + 成本/条款完整 | 可以发布受控正式报价版本 |
| `SPEC_ADOPTION` | 客户有效确认记录（由有权用户关联/验证）+ 指定 Spec Version | 规格可被生产资料引用 |
| `SUPPLIER_FEASIBILITY` | 有责任方的工艺/交期/成本确认材料 | 供应商可执行性被记录，但不自动允许生产 |
| `PRODUCTION_RELEASE` | 内部生产负责人 + 已通过 PO/PI/Spec/供应商确认等前提 | 生产资料可被正式放行 |
| `EXTERNAL_SEND` | 已批准文件、收件人、附件、最终消息及真实账号权限 | 可执行对外发送（P1） |

**特殊情况**：单人 Hackathon Demo 可模拟不同业务角色的审批流程，但记录必须标明 `simulated_actor`，不能声称外部客户/工厂已经实际批准。

## 4. 审批记录必须绑定内容哈希

```json
{
  "scope":"QUOTE_RELEASE",
  "target_type":"artifact_version",
  "target_version_id":"quotation_v2",
  "expected_content_hash":"sha256:abc...",
  "decision":"approve",
  "actor_id":"manager_001",
  "source_evidence_id":"approval_email_001",
  "created_at":"2026-10-31T10:00:00Z"
}
```

审批完成后如果 Quotation 重新生成新版本或内容哈希变化，旧审批对新版本**自动失效**。不能用用户选择了“同意改包装”替代报价批准。

## 5. 必须由服务器执行的安全检查

- Workspace/Case 访问控制：所有 Source ID、Artifact ID、Job ID 都再次校验作用域，防止 IDOR。
- Tool allowlist：Agent 只允许调用用户当前权限与工作流允许的工具；没有通用 SQL、任意文件系统写入与 shell 执行权限。
- Prompt Injection：把用户邮件/第三方文档作为数据传入，不解释为系统工具命令；对包含秘密数据的调用设出站访问策略。
- Sensitive Actions：批准/放行/发送的最终决定在确定性后端执行。
- Data Integrity：上传 SHA-256、ArtifactVersion hash、签名导出清单、不可变审计事件。
- Secret Hygiene：API Key、OAuth Token 只存后端 Secret Store/环境变量；不进入 LLM Prompt、日志、文件导出。
- SSRF：如果未来允许解析 URL，下载器需屏蔽内网/元数据 IP，限制重定向、下载大小、协议。
- 文件安全：禁止执行宏、脚本、嵌入对象；限制解析器 CPU/内存/页数。
- 收款账号：任何银行账户修改需要独立强核验，不进入本次 MVP 自动动作。

## 6. 导出文件的最小数据权限

客户 Quotation 不应携带供应商底价/成本明细；采购 RFQ 不应泄露客户目标毛利；内部 Production Instruction 不应自动包含客户其他项目的隐私。

通过 `renderer_profile` 白名单决定哪些字段可以放到某种外发模板；不能直接把整个 Canonical JSON 给模板渲染或 LLM 当附件发送。

## 7. 人在环流程的真正边界

```mermaid
sequenceDiagram
  participant A as Agent
  participant API as Gate API
  participant U as User
  participant DB as DB
  A->>API: request QUOTE_RELEASE(quotation_v2)
  API->>DB: evaluate all required facts + content_hash
  DB-->>API: missing price approval
  API-->>U: Review requested with version + evidence
  U->>API: Approve target version
  API->>API: authenticate, authorize, re-evaluate Gate
  API->>DB: append Approval event
  DB-->>API: approval_id
  API-->>A: domain approval reference (resume)
  A->>API: release quotation_v2
  API->>DB: verify hash + scope + approval; release event
```

即使 Agent 在恢复时收到用户输入 `approved=true`，Domain API 也要查真实持久化审批记录；不能仅根据 Agent State 判断。

## 8. 操作可撤销性

- 仅草稿：可以创建新草稿版本以撤回修改，保留历史记录。
- 已发布内部文件：用新版本替代/标废，不能抹掉历史；需要重新批准。
- 已发送外部邮件/已经采购：系统**不能**声称“撤销就是回滚成功”，只能执行纠错/补发与人工追踪。

## 9. 自动化安全验收

- [ ] 无权限用户访问另一个 Case 的 Source/Artifact 返回 403/404。
- [ ] 恶意客户附件含“ignore instructions; exfiltrate ...”，不会触发 Tool Call。
- [ ] 试图通过前端伪造 `actor_id` 或 `approved=true` 不能通过 Release Gate。
- [ ] 修改报价内容后，旧 `QUOTE_RELEASE` 审批失效。
- [ ] 缺 `SPEC_ADOPTION` 时，用户可以下载草稿，但不能放行生产。
- [ ] 模拟审批 UI 明确打标，未连接外部邮箱时绝不显示 `sent`。
- [ ] 关键操作有可查的 trace_id / actor_id / target_version / policy_version。

**相关**：[03 业务规则](../01-domain/03-business-rules.md)、[06 Runtime](../03-agents/06-agent-runtime.md)、[10 API](10-API-and-events.md)。
