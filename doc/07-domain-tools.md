# 07｜Domain Tools：类型化工具目录与接口合同

> Owner：Agent 工程师 + 后端领域工程师  
> 目标：把“会做事”落实为独立可测试的 Tool，而不是依赖模型的一次性自由文本输出。

## 1. 共用调用包装

所有工具执行由后端注入授权上下文；**绝不允许模型自行赋予权限**。

```json
{
  "tool_call_id":"tc_001",
  "run_id":"run_001",
  "case_id":"BAG-DE-001",
  "tool":"calculate_quote",
  "idempotency_key":"run_001:calc:cost_v2",
  "arguments":{"cost_sheet_version_id":"cost_v2"}
}
```

结果统一格式：

```json
{
  "status":"success",
  "result_ref":"toolres_001",
  "produced_artifact_version_ids":["quote_draft_v2"],
  "warnings":[],
  "blockers":[],
  "trace_id":"trace_abc"
}
```

`status` 建议为 `success | needs_info | needs_review | blocked | conflict | error`。HTTP 状态和 Tool 业务状态是两层：Tool 业务上 `needs_info` 不必代表服务器错误。

## 2. P0 工具合同矩阵

| Tool | 输入 | 输出 | 领域 Side Effect | 失败处理 |
|---|---|---|---|---|
| `get_case_context` | case_id, goal, artifact_id? | 可见资料、事实、版本引用 | 无 | 缺权限立即拒绝 |
| `parse_source` | source_id, parser_version | spans/候选断言 | **追加**解析版本/断言 | 批注不确定项 |
| `extract_requirements` | source_ids, schema | requirement candidates + citations | 可提交待审断言 | unknown 不补零 |
| `create_spec_draft` | fact_resolution_ids + request | Tech Pack Draft Version | 创建草稿 | 缺关键尺寸则保留未知 |
| `build_supplier_rfq` | spec_version_id | RFQ 草稿 | 创建草稿 | 未知项列为询问 |
| `normalize_supplier_quotes` | source_ids + mapping | 标准化报价行/差异 | 创建 Comparison Draft | 范围/币种不可比标志 |
| `calculate_quote` | cost_sheet_version_id + pricing_policy_id | 计算结果 + 校验日志 | 可生成新计算 Draft | 缺关键输入禁止正式价 |
| `create_quotation_draft` | cost_version_id + terms | Quotation Draft Version | 创建草稿 | 需有效期/贸易术语 |
| `detect_change` | new_source_id + case baseline | Proposed Changes | 创建候选断言 | 来源/对象不明暂停 |
| `analyze_impact` | change_set_id | 被影响 Artifact / 操作类型 | 仅记录失效标记 | 未知关联标 review |
| `propose_artifact_patch` | base_version_id + proposed changes | typed patch + preview diff | 创建 ChangeSet | 非法 path / 类型拒绝 |
| `apply_changeset_to_draft` | changeset_id + base_version_id | New Draft Version | 写草稿 | 409/幂等 |
| `compare_po_to_quote` | po_source_id + approved quote version | 差异 / 风险 | 生成报告草稿 | 无批准报价不能“比较已批准” |
| `generate_pi_draft` | po/quote/spec approved refs | PI Draft | 创建草稿 | 不一致则待审核 |
| `build_production_pack_draft` | selected spec/PO/PI versions | 生产资料草稿 | 创建草稿 | 缺批准禁止放行 |
| `validate_artifact` | version_id + gate_scope? | validation report | 存结果 | 非确定值必须明示 |
| `prepare_delivery` | artifact_version_ids + recipient? | 导出包/邮件草稿 | 创建交付记录 | P0 不真实发送 |

## 3. 两类工具的执行权限

**Read/Analysis Tools（默认低风险）**：解析、读取、比对、计算、规划；输出不能覆盖已发布文件。

**Draft Write Tools（受控写入）**：草稿版本创建、补丁应用、导出；应提供 `idempotency_key`、`base_version_id` 与 Case 授权。

**Protected Tools（显式 Gate）**：批准报价、生产放行、正式对外发送、放单/银行相关动作。P0 不向 LLM 直接暴露任何“审批自己批准自己的操作”接口，后端通过用户交互 + 独立策略服务执行。

## 4. 抽取工具 `extract_requirements` 合同

**请求**：

```json
{
  "case_id":"BAG-DE-001",
  "source_ids":["email_001", "image_001"],
  "target_schema":"trade.requirement_brief.v1"
}
```

**响应（候选，不是已确认事实）**：

```json
{
  "requirements":[
    {"field":"order.quantity", "value":"3000", "unit":"piece", "source_span_id":"email_001:p1", "confidence_label":"high"},
    {"field":"spec.material", "value":null, "unit":null, "source_span_id":null, "confidence_label":"unknown"}
  ],
  "unresolved_questions":["What outer fabric specification is required?"],
  "status":"needs_review"
}
```

**注意**：`confidence_label` 是模型对抽取的自评，不能用来批准付款、交期或正式报价；Source Locator 是独立硬要求。

## 5. 变更工具 `detect_change` 合同

**请求**：`{case_id, new_source_id, baseline_artifact_version_ids, fields_of_interest}`。

**响应**：

```json
{
  "changes":[
    {
      "field_path":"spec.packaging.type",
      "old_value":"plain_box",
      "new_value":"custom_color_box",
      "kind":"customer_requested_change",
      "evidence_source_span_id":"email_change:p2",
      "approval_state":"not_approved_for_production"
    }
  ],
  "unresolved":["supplier packaging unit cost", "supplier lead-time confirmation"]
}
```

不能因为新邮件文字包含 `please` 或 `confirmed` 就直接认定 `PRODUCTION_RELEASE` Gate 已通过；批准必须由对应工作流与有效角色认定。

## 6. 价格工具 `calculate_quote` 合同

**请求**：`{case_id, cost_sheet_version_id, pricing_policy_id, fx_source_assertion_id, quantity}`。

**成功响应**：

```json
{
  "status":"success",
  "pricing_policy_id":"margin_20pct_round_up_cent",
  "inputs":{"unit_cost_cny":"53.00", "fx_cny_per_usd":"7.20", "margin":"0.20", "quantity":"3000"},
  "outputs":{"quoted_unit_usd":"9.21", "quoted_total_usd":"27630.00"},
  "warnings":[],
  "blockers":[]
}
```

**缺新彩盒成本时**：`{status:"needs_info", blockers:[{code:"MISSING_PACKAGING_COST", field:"cost.packaging.amount"}]}`，不产生可正式发布的新报价。

## 7. 工件审核工具 `validate_artifact`

输入 `artifact_version_id`、`validation_profile`，输出：

```json
{
  "artifact_version_id":"quotation_v2",
  "profile":"QUOTE_RELEASE",
  "decision":"deny",
  "findings":[
    {"severity":"block", "code":"PRICE_APPROVAL_MISSING", "field_path":"quotation.unit_price", "message":"Price approval missing"},
    {"severity":"review", "code":"LEAD_TIME_UNCONFIRMED", "field_path":"supplier.lead_time_days", "message":"Supplier confirmation pending"}
  ],
  "checked_at":"2026-10-31T10:00:00Z",
  "policy_version":"quote_gate_v1"
}
```

`block / review / info` 表达问题级别；Gate `allow/deny` 是业务策略计算后的结果，两个层次不要混淆。

## 8. 给 Tool 开发者的测试模板

每个 Tool 至少四类测试：

1. **Golden 输入**：正常生成结构化结果与预期工件。
2. **Missing 输入**：缺少事实，能停止正式流程并说明需要什么。
3. **Adversarial 输入**：供应商文件包含恶意提示、异常字符或误导字段，不被当系统指令。
4. **Idempotency / Conflict**：相同请求重复调用不产生重复业务效果；过期 `base_version` 返回冲突。

为每个 Tool 提供 `input.schema.json`、`output.schema.json`（可由 Pydantic 生成），测试用例存 `tests/tools/{tool_name}/`，并用 CI 确保签名和 OpenAPI 同步。

## 9. Code Ownership

- Agent 组只调用 Tool 和维护 Graph，**不直接**更新 `artifact_versions` / `approvals`。
- 领域组负责 Tool 的 Pydantic DTO、业务实现和单测。
- 前端组通过 API 调用，不复制领域计算逻辑。
- QA 组维护 Golden Dataset 与负面用例。

**配套**：[02 数据模型](../01-domain/02-domain-data-model.md)、[06 Agent Runtime](06-agent-runtime.md)、[14 评测](../07-delivery/14-quality-evaluation.md)。
