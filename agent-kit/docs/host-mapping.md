# Agent Kit 与宿主接入

核对基线：`origin/lirui@5fcf0a1`，合入 `justike@4e34ce0`。独立模块提交为 `d23ab0a`。随后新增真实宿主适配器；下面记录实现边界。真实模型和浏览器主线尚未验收，API 离线测试不代表 M5 最终完成。

## 安装与启用

在同一个 Python 3.12+ 环境执行：

```powershell
python -m pip install -e './agent-kit[test]' -e './backend[test]'
python -m pytest backend/tests agent-kit/tests -q
```

`backend/.env` 设置 `AGENT_FILE_TOOLS=1`、`MODEL_NAME`、`MODEL_API_KEY`，可选 `MODEL_BASE_URL`。`python dev.py` 启动 API、Worker 和 real 模式前端。开关默认 0；启用后，对话入口的询盘理解、报价和包装变更使用真实工具循环。缺少模型时明确失败，不降级到预设业务流程。

## 字段与职责映射

| Agent Kit | 真实宿主映射 |
| --- | --- |
| `ExecutionContext` | 从已认证用户、Case、Job、Run 和已领取 WorkItem 构造。generation 为租约代数。每次操作检查权限、Run 基线、active Run、租约代数/状态/期限。模型不能传入权限。 |
| `FileRef` | Evidence ID → Blob；输出 Blob ID → agent_file Item。公司资产版本和本人画板附件先由现有授权函数解析，再进入冻结清单。原文、粘贴证据、用户任务消息和所选文字资料版本作为带哈希的 TXT 来源。物理路径只由适配器解析。 |
| `Citation` | 保存于受控快照及 agentRecord.ref.inputs；绑定文件 ID、哈希、页/表/单元格/段落定位和摘录。工具检查引用存在，语义正确性另验收。 |
| `ArtifactRef` | Case/成果类型稳定逻辑 ID；不可变 artifact Item 版本。agentRecord 保存快照、来源、计算、差异、文件和独立状态。宿主行 ID 用于批准/导出。与现有版本共同 CAS；人工或旧 JSON 成果需协调，不静默覆盖。 |
| `ToolResult` | agent_result Item 保存实际结果；现有 Idempotency 表按 Case/Job/工具键绑定请求哈希和响应，与成果登记和事件在同一 SQLite 写事务提交。跨租约重试复用相同写入。 |
| `ExecutionEvent` | 现有 run_event Item；Run.last_seq 分配序号。agent.* 类型带公开摘要和结果引用，不新建业务数据库。 |
| 检查点 | LangGraph SQLite checkpointer，Case/Job 绑定线程，路径 FILE_GRAPH_CHECKPOINT_DB。业务状态、文件和批准仍由现有服务管理。 |
| 交付清单 | Run.fileOutputs 含实际文件、哈希和授权下载 URL；Case Revision 绑定成果、文件、冻结输入。指定 artifactVersionId 复用已生成字节，不用内部 JSON 重渲染客户文件。 |

实现：`backend/app/agent_files.py`、`file_worker.py`。宿主 `agent.py:price_quote` 仅转换旧 DTO，委托同一个 Agent Kit Decimal 计算器。前端 Mock/旧演示计算不作为真实业务计算来源。

## 输入、继续与状态

对话默认冻结当前 Case 证据；显式 inputRefs 时使用所选证据。前端提交当前用户画板 canvasFileIds，服务端重新校验归属。公司资产通过 assetVersionIds，文字资料通过 sourceVersionIds 明确选择。个人资产禁止进入协作 Case。哈希变化、资料撤销、越界引用均拒绝。

可直接说“汇率7.20，毛利20%”。宿主保守解析明确依据，在 Case 内保存供后续变更复用；假设或否定不创建确认事实。其他语义字段可引用冻结用户消息。附件文字按数据处理。

needs_info → Run/Job needs_input、WorkItem waiting；已有草稿可下载。上传补价并回答当前问题后，在同一 Job/Run 继续，冻结补充证据和回答文本，无需重填可从文件读取的供应商成本。当前前端将一次对话补充映射到各待答问题，复杂逐项选择仍使用原交互。

needs_review 可对应 Run succeeded / Job needs_review。blocked/conflict/error 对应失败，保留成功文件。生成、宿主投影、内部批准、客户接受分别记录；工具无批准或外发能力。现有商业批准仍要求绑定供应商报价及业务验证；本次文件草稿不自动满足该批准条件。

## 验收边界

`backend/tests/test_agent_file_tools.py` 使用实际 FastAPI、SQLite、Blob、Artifact、事件、授权下载及 LangGraph；模型为明确标记的离线替身。覆盖下载越权、冻结输入、租约失效、幂等、暂停继续、旧版保护、客户字段隔离、资产/资料权限、撤销和无模型显式失败。

真实模型解释、假设/否定、注入抵抗，以及浏览器上传→对话→补证→下载尚待模型配置后验证。类型检查、前端单测和构建不能替代该主线。DOCX/XLSX 未做 Office 视觉验收。见 [verification.md](verification.md)。并行扩展目录各有交付说明；代码合入不表示已注册到报价运行时。