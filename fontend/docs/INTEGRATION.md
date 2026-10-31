# API 联调与页面状态

统一来源是任务包配套 V1.0 契约；`src/api/types.ts` 为前端当前消费的类型。部分文档未明确的响应包采用以下暂定约定，需要 B/C/D 联调评审，不能把它们当作已发布 OpenAPI。

## 新版 real 模式契约

新版首页统一进入 `/inquiries/:id`。画板、Wiki、个人/公司资产、收藏、技能目录与 LangGraph 澄清恢复已经接通真实后端，完整端点和校验规则见 [适配说明 v1.1](../../doc/Frontend_Backend_Adaptation_v1.1.md)。待回答任务通过 `Inquiry.pendingRunId` 恢复；Run 可返回 `clarification` 和 `completedPhases`。补充回答继续同一 Run，画板 editVersion 与业务 Revision 各自独立。旧工作台保留为原件、核价和业务审批入口。

## 传输约定

- `api.get/post/put/patch/delete/request` 使用相对路径，如 `/me`、`/workspaces/ws_1/inquiries`。
- `GET /me` 与 `POST /auth/session` 暂消费 `Session {user:{id,name,role},workspace:{id,name}}`。真实登录提交 `{email,password}`，须适配团队实际认证。
- 列表响应 `{items,nextCursor,matchedCount}`；消息、版本及资源消费 `{items}`。
- 汇总响应 `{todo,active,waiting,done}`；它与搜索列表分别请求，搜索不改变全量计数。
- 单对象响应直接为类型对象。正式服务返回 `requestId`，adapter 保留该字段；Mock 成功响应暂不附加 requestId，所有错误携带 requestId。错误格式 `{error:{code,message,details,fieldErrors},requestId}`。
- 创建及 POST 请求带 `Idempotency-Key`。写操作不自动重试。新建询盘同一次正文重试保留幂等键；用户修改正文后使用新键。
- API 请求带 Cookie，生产必须采用同源路由或明确配置 CORS/CSRF。权限最终由服务端验证。
- AbortController 取消读请求，过时结果不得覆盖新页面。超时、网络及非 JSON 错误统一显示。

## 运行与草稿

目前前端采用契约允许的 GET Run 状态轮询，约 900ms；活动 Run 从询盘详情恢复，运行完成后重新获取完整版本。未使用流式片段组装 Revision。后续可在 adapter/hooks 加入可恢复 SSE，保留轮询降级。

草稿 PUT 携带 `baseDraftVersion`；409 `DRAFT_CONFLICT` 的 details 暂消费 `currentDraft` / `latestDraft` 或文本/版本字段。草稿、Revision、元数据的版本号互相独立。编辑后重新审校，导出锁定指定 Revision、两语 draftVersions、assetVersionIds。

素材引用暂采用 `${asset.id}:v${asset.version}` 固定版本标识；Run 输入 `assetVersionIds` 由 Mock 检查 SKU 范围，并只在成功新业务版中写入。此标识格式需与 C 的正式 AssetVersion ID 对齐。材料清单绑定明确的业务版、两语草稿版、素材及来源版本；提交 `bundleId` 导出时不能同时提交另一套版本字段。

导出响应暂消费 `{exportId,status:'pending'|'ready'|'failed',downloadUrl?,error?}`；pending 时查询导出任务，下载走授权地址。Mock 可返回转义后的 html 用于浏览器下载，真实模式不使用该字段替代服务端下载。

## 页面状态清单

| 场景                   | 呈现与恢复                               |
| ---------------------- | ---------------------------------------- |
| 首次加载               | 显示加载，计数未返回不显示假零           |
| 搜索空 / 无询盘        | 区分无匹配与新建指引                     |
| 请求失败               | 错误消息与请求编号，提供重试并保留表单   |
| 会话过期               | 重新登录弹窗；未确认修改不标成功         |
| 无权限 / 不存在        | 显示授权错误，不补本地假数据             |
| Run 活动中             | 当前询盘写入禁用；其他询盘可处理；可取消 |
| Run 失败 / needs_input | 保留上一版本；显示原因或澄清问题         |
| 已结束 / 历史          | 只读；已结束可显式重开                   |
| 保存中 / 失败 / 冲突   | 分开显示；失败可重试；冲突比较后处理     |
| 断网                   | 全局连接提示；写入结果不冒充成功         |
| 资源导入错误           | 行号、字段、错误消息；有错误不能发布     |
| 导出校验阻断           | 硬错误显示，不能绕过检查下载             |

## Mock 的边界

IndexedDB 数据库 `easywork-mock-v1` 仅承载本浏览器合成测试状态，使用 idb。重置示例可在浏览器开发工具删除该数据库；此操作会删除此浏览器的演示记录。清理正式服务数据不走此路径。

Mock 使用固定示例、模拟延时、测试规则与故障，不是认证或业务服务实现。新原文不能由 Mock 真实理解；真实安全隔离、模型质量、跨设备读取、后台服务重启恢复均等待服务端验收。历史业务 Revision 与草稿修订保留；Mock 支持通过 `locale` 和 `draftVersion` 回读已保存的历史草稿。资源语义、真实 Schema 和附件授权需与 C/B 对齐。
