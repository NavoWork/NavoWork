# 12｜本地部署、环境配置、持久化与可观测性

> Owner：全栈 / DevOps ｜ P0 目标：团队开发环境可重复启动、Agent 断网可恢复、Demo 不依赖某个开发者的本地文件。

## 1. 推荐部署形态

Monorepo + Docker Compose：

```text
Browser ──HTTPS/localhost──> web (Next.js)
              │
              └──> api (FastAPI) ──────> postgres (domain + checkpoint)
                              ├───────> minio (source + exports)
                              └───────> worker (runs + parsing + rendering)
                                            └──────> model API / local VLM
```

**注意**：Worker 与 API 可共用同一 Python 包，但必须能独立启动。开发最初可用单 worker 和数据库任务表轮询；若任务吞吐/并发要求提高再引入 Redis + RQ/Celery。

## 2. 环境变量（示例名称，不提供真实密钥）

```dotenv
APP_ENV=development
API_BASE_URL=http://localhost:8000
WEB_BASE_URL=http://localhost:3000
DATABASE_URL=postgresql+psycopg://trade:****@postgres:5432/trade
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_BUCKET=trade-artifacts
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...
MODEL_PROVIDER=...
MODEL_NAME=...
MODEL_API_KEY=...
PARSER_MAX_FILE_MB=20
RUN_MAX_TOOL_STEPS=30
```

不要将 `.env` 提交仓库；提供 `.env.example`，用本地 Secret 文件或 CI Secret 管理真实值。

## 3. 服务启动和 schema 初始化

建议项目 Makefile：

```bash
make up            # docker compose up -d
make migrate       # alembic upgrade head
make seed-demo     # 写入演示 Case 和原始 fixture
make test          # pytest + 前端测试
make eval          # 运行 Golden Dataset
make down          # 停止容器（不清空数据）
```

命令是**建议的项目目标接口**，不是已经存在的可运行命令。Code Agent 需要在实现仓库中提供对应配置。

## 4. 数据存储与持久化策略

- PostgreSQL Domain Tables：与业务事实相关的表，必须备份。
- PostgreSQL LangGraph Checkpoints：可以放同一个实例、独立 schema，生命周期不同于业务数据；不要将 Checkpoint 当业务主数据。
- MinIO：`sources/{workspace}/{case}/{source_id}`、`exports/{workspace}/{case}/{delivery_id}`，对象 key 不直接包含原始客户文件名。
- `job_events`：持久追加，SSE 重连/调试依赖它，不能只写进内存日志。
- 事务一致性：数据库更新 + outbox/event 的写入需在同一事务，外部异步处理允许重试并幂等。

## 5. API/Worker 重启时的行为

- 已存的 Source/Artifact 保留，Worker 重新取 `queued/running` 但 Lease 过期的 Run。
- 对于中断待审批的 Job，从 Checkpointer 恢复；不得新开一个逻辑上相同的写操作。
- ToolInvocation 幂等键确保恢复时已成功提交的操作不会重新发布。
- 如果导出器崩溃，`deliveries.status=failed/retryable` 与重试次数可查。
- 仅模型响应成功但 Domain Tool 尚未提交时，不能对外声称该 Job 已完成。

## 6. 最小可观测性

推荐每次业务请求附带以下关联字段：

`request_id / trace_id / workspace_id / case_id / job_id / run_id / tool_call_id / artifact_version_id`

日志级别：
- INFO：Job 开始/结束、Tool 名称、文件导出完成、Gate 结果（不含敏感内容）。
- WARN：缺资料、来源冲突、审批待处理、解析不确定。
- ERROR：工具失败、版本冲突、权限拒绝、导出校验失败。

关键指标：
- Run 成功率 / 阻断率 / 平均恢复次数。
- Parser 字段级召回/精确率（Golden Dataset）。
- 成本计算测试通过率。
- Artifact 版本冲突次数、ChangeSet 被拒次数。
- 非授权发布/发送次数（必须为 0）。
- 交付物导出与二次验证成功率。

## 7. 成本与性能约束

- 限制一次任务最大输入页数、最大工具步数、模型预算和 Worker 运行时间；具体阈值需要基于真实文档样本测量。
- 大文件先按类型解析并挑选相关 Source Span；不要把原文全部塞入 Agent Prompt。
- 对重复文件与解析模型版本做缓存；业务数值计算全部本地确定性完成。
- 记录每次模型调用的 provider、model、token usage（若 API 支持）和 latency，以便后期做 ROI 对比。
- 失败模型调用可重试；写入/对外副作用必须安全幂等。

## 8. 部署安全

- API 和 MinIO 默认仅内网/开发环境访问；对公网部署需 TLS、认证、服务间权限与安全审计。
- PostgreSQL 不允许公众可访问端口；对象存储 Bucket 禁止匿名公开。
- 模型 API 调用时明确第三方数据传输边界；如果使用私有报价/客户邮件，需经团队确认合规的数据处理方式。
- 正式部署需要文档保留期、删除/备份策略与个人数据处理规则；Hackathon 演示尽量使用模拟数据。

## 9. CI 最低要求

- Python：ruff/lint、mypy 可选、pytest 单元+集成。
- TypeScript：typecheck、lint、基础 UI 测试。
- 数据库：Alembic 能在空库顺利迁移；迁移演练不能破坏测试数据。
- API：OpenAPI 及前端类型同步；重要 Schema 变更触发契约快照检查。
- Golden Evals：报价数值、审批门禁、跨 Case、重复执行等自动测试。

## 10. 启动验收

- [ ] 新开发成员克隆仓库后，按 README 可启动 web/api/worker/postgres/minio。
- [ ] `seed-demo` 能生成同样的 BAG-DE-001 样例环境。
- [ ] 重启服务，草稿文件、Source、Job Event 和待审批 Run 仍可恢复。
- [ ] 浏览器刷新后 Event Stream 可以续传。
- [ ] 模型 API 不可用时，确定性报价工具和页面仍可独立展示/测试。
- [ ] 演示环境不使用任何真实客户银行信息或未授权内部资料。
