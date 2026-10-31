# 10｜Backend API、HTTP 合同、SSE Event Protocol

> Owner：后端 API 工程师 + 前端工程师 ｜ 版本：API Draft v1（合同评审用）

## 1. API 原则

- 以 `/api/v1` 为前缀；路径同时体现 Case/Job/Artifact 资源关系。
- 服务器端按照已认证用户授权解析 `workspace_id`、`case_id`，不可只依赖 URL 参数。
- 输入输出用 Pydantic 生成 OpenAPI/JSON Schema；前端可以自动生成 TypeScript Client。
- 所有修改操作携带 `Idempotency-Key` 和对版本敏感操作的 `base_version_id`；建议支持 `If-Match`/ETag。
- **草稿生成与正式发布分离**；`POST /approvals` 是独立动作，并校验角色、范围、目标版本哈希。
- 长任务接口立即返回 `run_id` 和当前状态，不持有长 HTTP 请求直至 LLM 全部执行完。
- Job Event 持久化，SSE 只是读取事件的通道，不是唯一消息来源。

## 2. Endpoint 清单（P0）

| Method | Path | 用途 | 关键响应 |
|---|---|---|---|
| `POST` | `/cases` | 创建 Case | `{case_id}` |
| `GET` | `/cases/{case_id}` | Case 详情、当前 Job/Artifact | Case View |
| `POST` | `/cases/{case_id}/sources` | 上传文件 | `{source_id, parse_status}` |
| `GET` | `/cases/{case_id}/sources` | 资料列表 | Sources |
| `GET` | `/cases/{case_id}/facts` | 断言与有效事实（按 field/scope） | Facts + provenance |
| `POST` | `/cases/{case_id}/jobs` | 创建 Job/Run | `{job_id, run_id, status}` |
| `GET` | `/runs/{run_id}` | 当前 Run 快照 | status, steps, pending_action |
| `GET` | `/runs/{run_id}/events` | SSE 持久事件 | `id`, `event`, `data` |
| `POST` | `/runs/{run_id}/resume` | 审批/补资料后的恢复指令 | `{status}` |
| `GET` | `/cases/{case_id}/artifacts` | 成果树 | logical_artifacts |
| `GET` | `/artifacts/{artifact_id}` | 当前草稿、发布指针和版本 | Artifact View |
| `GET` | `/artifacts/{artifact_id}/versions/{version_id}` | 指定版本快照 | Canonical Content |
| `POST` | `/artifacts/{artifact_id}/draft-patches` | 提出/应用草稿修改 | ChangeSet / Draft Version |
| `POST` | `/changes/{change_set_id}/review` | 接受/拒绝候选修改 | ChangeSet status |
| `GET` | `/changes/{change_set_id}/diff` | 字段级 diff | before/after/findings |
| `POST` | `/approvals` | 以当前认证角色提交业务审批 | Approval Event |
| `POST` | `/artifacts/{artifact_id}/release` | 后端执行 Gate 并发布指定版本 | release event / gate result |
| `POST` | `/deliveries` | 构建交付包（草稿/发布版本） | `{delivery_id,status}` |
| `GET` | `/deliveries/{delivery_id}` | 导出结果及下载项 | manifest + URLs |

**P0 不提供**邮件真实发送、付款、放单、ERP 生产开工接口。

## 3. 创建 Agent Job

Request:

```http
POST /api/v1/cases/BAG-DE-001/jobs
Content-Type: application/json
Idempotency-Key: create-job-001
```

```json
{
  "goal":"客户把普通包装改为定制彩盒，请重新报价",
  "job_type":"revise_quotation",
  "active_context":{
    "artifact_id":"cost_sheet_001",
    "version_id":"cost_v1",
    "selected_field_path":"cost.items.packaging.amount"
  },
  "input_source_ids":["email_change_007"]
}
```

Response（202 Accepted）:

```json
{
  "job_id":"job_100",
  "run_id":"run_100a",
  "status":"queued",
  "events_url":"/api/v1/runs/run_100a/events"
}
```

**后台流程**：创建 Job/Run、入队（数据库 Pending Job 或消息队列）、提交事务；Worker 接手。不能把客户端提交的 `source_ids` 当作已授权，否则可能跨 Case 读取。

## 4. 修改 Artifact 草稿

Request:

```http
POST /api/v1/artifacts/cost_sheet_001/draft-patches
Idempotency-Key: patch-abc-001
If-Match: "cost_v1"
```

```json
{
  "case_id":"BAG-DE-001",
  "base_version_id":"cost_v1",
  "operations":[
    {"op":"replace", "path":"cost.items.packaging.amount", "from":"2.00", "to":"5.00", "source_assertion_id":"fa_supplier_005"}
  ]
}
```

Response（200/201）：

```json
{
  "change_set_id":"cs_008",
  "new_draft_version_id":"cost_v2",
  "validation_report_id":"val_014",
  "affected_artifacts":["quotation_001", "production_instruction_001"]
}
```

若已被其他操作更新：HTTP `409`，Body：`{code:"ARTIFACT_VERSION_CONFLICT", latest_version_id:"cost_v2"}`；前端保留旧草稿并引导重算。

## 5. 审批与放行接口

**提交审批**：

```json
{
  "case_id":"BAG-DE-001",
  "scope":"QUOTE_RELEASE",
  "target_type":"artifact_version",
  "target_version_id":"quotation_v2",
  "expected_content_hash":"sha256:...",
  "decision":"approve",
  "note":"Commercial price reviewed"
}
```

身份与权限来自服务端 Session，`actor_id` **不得由客户端指定**。审批成功并不自动触发其他 Scope 的授权。

**发布**：

```json
{
  "target_version_id":"quotation_v2",
  "release_scope":"QUOTE_RELEASE",
  "expected_content_hash":"sha256:..."
}
```

服务器重新计算 Gate，并检查目标版本哈希与审批匹配。审批后版本改变，原审批不适用于新版。

## 6. 统一错误结构

```json
{
  "error":{
    "code":"MISSING_REQUIRED_FACT",
    "message":"Supplier packaging cost is not verified",
    "details":[{"field_path":"cost.packaging.amount", "reason":"not_confirmed"}],
    "trace_id":"trace_001"
  }
}
```

建议 Code：
- `CASE_ACCESS_DENIED` (403/404)：无权限/不存在；为防枚举外部可统一返回 404。
- `ARTIFACT_VERSION_CONFLICT` (409)：基线版本过期。
- `INVALID_DOMAIN_VALUE` (422)：数值/单位/货币错误。
- `MISSING_REQUIRED_FACT` (业务阻断，不必 HTTP 500)。
- `APPROVAL_REQUIRED` (409 或业务结果 deny)：发布不满足 Gate。
- `PARSER_FAILED`、`EXPORT_VALIDATION_FAILED`、`RUN_RECOVERY_FAILED`（明确用户可采取动作）。

## 7. SSE Event 协议

```text
id: 42
event: tool.succeeded
data: {"run_id":"run_100a","seq":42,"tool":"calculate_quote","summary":"Quoted unit USD 9.21","artifact_version_ids":["cost_v2"]}

id: 43
event: approval.requested
data: {"run_id":"run_100a","seq":43,"scope":"QUOTE_RELEASE","target_version_id":"quotation_v2"}
```

- `id` 是同一 Run 内单调递增事件序号；`GET ?after_seq=42` 或 `Last-Event-ID:42` 重新连接。
- 事件从持久 `job_events` 表读；SSE 是 at-least-once 展示，客户端按 `(run_id,seq)` 去重。
- 心跳注释可维持连接，敏感 Tool 参数不可直接推流。
- 返回 UI 前应过滤内部模型推理、Secrets、未授权来源片段。

## 8. PDF/XLSX 下载与权限

下载链接可采用短时签名 URL，但生成前必须验证用户的 Case/Artifact 授权；URL 超时、不可枚举，并记录导出行为。文件名仅用于展示，Object Key 由后端生成。

## 9. 合同测试建议

1. 从 Pydantic 导出 `openapi.json`，前端 TypeScript 类型自动生成或 CI 校验。
2. 每个 Endpoint 至少测试：成功、无权限、缺参数、版本冲突、重复幂等、失效版本审批。
3. OpenAPI 示例与 Golden Dataset 一致；定价数字 `Decimal` 序列化为 string。
4. SSE 重连不会丢未消费事件；Run 失败时有终止事件。
5. 审批 API 即使绕开 UI 也无法越权。

**配套**：[02 数据模型](../01-domain/02-domain-data-model.md)、[11 安全审批](11-security-approvals.md)。
