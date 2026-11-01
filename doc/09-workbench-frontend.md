# 09｜前端工作台：三栏 IDE、可编辑画布、Agent Panel、Diff 与审批

> Owner：前端工程师 ｜ 目标：不是“Chat + 文件列表”，而是一个人和 Agent 共同操作业务成果的工作环境。

## 1. 页面与信息架构

```text
/                       Work Home：继续 Job / 待我审核 / 开始新工作
/workspace/[caseId]     核心工作台
/workspace/[caseId]/review     Diff / Approval / Validation
/workspace/[caseId]/deliver    导出包 / 文件版本 / 历史
```

核心页三栏 + 底部抽屉：

```text
┌────────────────────── Case + Job + Export ───────────────────────────┐
│ 左：Source/Artifact 树 │ 中：Artifact Editor   │ 右：Agent Panel       │
│ 所有来源/版本           │ Tab: Spec / Cost /   │ 目标、计划、工具进度    │
│ 当前选中来源           │ Quotation / PI       │ 缺信息、下一步、执行    │
│ 点击文件定位           │ 可直接编辑及查看来源 │ [暂停][生成][审核]     │
├─────────────────────────────────────────────────────────────────────┤
│ 底部：Source Inspector | Validation | Diff | Run Event Log          │
└─────────────────────────────────────────────────────────────────────┘
```

**首页**不要默认满屏 KPI / 订单卡片；首屏最重要的是「我现在需要完成什么工作」。

## 2. 前端状态分层

| 状态 | 谁拥有 | 例子 |
|---|---|---|
| UI 临时态 | React state | 当前 Tab、选中的 cell、面板展开 |
| 服务器业务态 | FastAPI + DB | Artifact 版本、Source、审批记录 |
| Job 实时态 | SSE + Run Events | 运行步骤、阻断、用户输入要求 |
| 编辑草稿态 | 本地 draft buffer + 服务器版本 | 尚未提交的单元格修改 |

建议 React Query/TanStack Query 管理服务端数据缓存；本地编辑期间保持 `base_version_id`，提交后由服务端响应提供新版本。

## 3. Active Context 协议

用户选中 `Cost Sheet` 中包装单价，然后发：“彩盒改成 ¥5，重新算报价”。前端发：

```json
{
  "case_id":"BAG-DE-001",
  "job_goal":"包装改成彩盒，重新算报价",
  "active_context": {
    "artifact_id":"cost_001",
    "artifact_version_id":"cost_v1",
    "selected_field_path":"cost.items.packaging.amount"
  },
  "allowed_actions":{"external_send":false,"draft_write":true}
}
```

该上下文帮助模型理解用户**正在操作什么**；Case 与权限由后端重新校验，不信任前端 `allowed_actions` 作为授权来源。

## 4. 编辑器策略

### 4.1 表格编辑

- 首选 AG Grid Community：Spec/Cost/Comparison 的业务数据表。
- `rowId` 和 `fieldPath` 稳定，显示单位、来源状态、是否可编辑；不用物理 Excel 坐标作为业务字段。
- 推荐将 Grid 设置成**受控编辑**：`readOnlyEdit=true`，在 `cellEditRequest` 中生成客户端 Patch，交由后端验证提交；避免 UI 私自改变已发布版本。
- 计算列用只读样式展示，重新计算由后端负责。
- **Community 不含原生 Excel Export、完整表格公式和高级范围选取等 Enterprise 特性**，P0 只用单元格编辑/排序/过滤；XLSX 由服务器 `openpyxl` 生成。

### 4.2 文字/说明

- 先用结构化表单 + Markdown/文本编辑器展示 RFQ、报价说明、邮件草稿；需要富文本时接 Tiptap。
- Tiptap 只负责编辑文档结构与内容，不负责金额计算或正式业务事实管理。

### 4.3 来源预览

- Source Tree 中点击 `Supplier A.xlsx:F12`：展示 Sheet + Cell 的对应区域，或至少提供定位标签与原值。
- PDF 预览先支持页码跳转与文本搜索；有可靠 bbox 时才做高亮。
- 产品图片可展示 VLM 可见观察区域，但尺寸 Unknown 必须明示。

## 5. Agent Panel 的信息架构

按顺序展示：

1. 当前目标与上下文（Case/Artifact，避免串单）。
2. 当前执行计划（步骤及状态）。
3. Tool 完成摘要（不展示密钥或内部模型推理）。
4. 需要补齐的事实/审批（明确谁、依据什么、影响什么）。
5. 输出文件卡片 / Diff / 下载。

避免将原始模型 token 流直接当业务操作日志；面板以持久 `JobEvent` 的结构化摘要为准。

## 6. Review 面板流程

```text
Agent 提出 ChangeSet
  ↓
字段差异表（before/after、source、risk）
  ↓
用户选择：接受草稿修改 / 拒绝 / 直接手工编辑
  ↓
POST /changes/{id}/review
  ↓
后端校验 base_version + 事务提交
  ↓
产生新 Draft Version
  ↓
若需要正式报价/生产发布：再走独立 Gate
```

**按钮命名必须精准**：
- `Apply to Draft`（应用到草稿）不是 `Approve Quotation`（批准报价）。
- `Approve Price for Release` 是内部报价批准，不代表发送给客户。
- `Record Customer Approval` 需要对应客户证据，不是随便点击即可假冒客户确认。
- `Export Draft` 与 `Release & Export` 分开。

## 7. 版本冲突与异步反馈

### 版本冲突（HTTP 409）

用户基于 `cost_v1` 编辑时，另一个 Tab/Agent 已生成 `cost_v2`：
- UI 不要覆盖；保留本地输入，弹出 `base v1 / current v2 / your proposal` 三方比较。
- 提供“重新应用建议”操作，生成新的 ChangeSet；不能静默合并敏感价格/数量。

### 任务重新连接

- Run 创建后返回 `run_id`，前端订阅 `/jobs/runs/{run_id}/events?after_seq=N`。
- 刷新页面先获取 Job/Run 快照，再从最近序号继续 SSE。
- 网络断开不等于 Run 失败；UI 状态分为 `connection_lost` 与 `run.failed`。

## 8. 核心组件（建议目录）

```text
components/
  workspace/CaseHeader.tsx
  workspace/ResourceTree.tsx
  workspace/ArtifactTabs.tsx
  workspace/SourceInspector.tsx
  editors/CostSheetGrid.tsx
  editors/TechPackEditor.tsx
  editors/QuotationEditor.tsx
  agent/AgentPanel.tsx
  agent/ExecutionTimeline.tsx
  review/ChangeDiffTable.tsx
  review/ApprovalGateDialog.tsx
  review/ValidationFindings.tsx
  delivery/DeliveryExportPanel.tsx
```

每个业务编辑器接收 `{artifactVersion, onProposePatch}`，**不直接写数据库**。

## 9. 用户体验验收

- [ ] 上传询盘后，用户可以在同一工作台查看来源、Agent 进度和生成的 Spec。
- [ ] 修改包装成本，自动显示本地待保存态，后端确认后显示新版本。
- [ ] 选择一个价格字段能反查供应商来源。
- [ ] 客户变更后至少三个 Artifact 的 Diff 在 Review 页面可查看。
- [ ] 未通过价格审批时，按钮不宣称“已正式报价”；后端也阻断发布。
- [ ] 刷新页面能看到同一个 Run 的历史和等待状态。
- [ ] 出错时展示可操作信息而不是“Agent 已完成”假反馈。

## 10. 技术验证来源

- AG Grid Cell Editing：https://www.ag-grid.com/react-data-grid/cell-editing/
- AG Grid Enterprise Excel Export：https://www.ag-grid.com/javascript-data-grid/excel-export/
- Tiptap Headless Editor：https://tiptap.dev/docs/editor/getting-started/overview
