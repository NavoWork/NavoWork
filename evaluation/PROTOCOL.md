# 独立适配器协议 navowork-eval/1

此协议只位于 `evaluation/`，是共享 `ExecutionContext/FileRef/Citation/ToolResult` 冻结前的替身协议，不定义或修改产品 contracts。结构索引见 `protocol.schema.json`；业务不变量由 `checker.py` 检查。JSON Schema 用于接入方查阅，不依赖第三方验证器，也不能代替业务校验。

## 调用边界

模块适配器实现 `run(request: dict) -> dict`；子进程从 stdin 读一个 UTF-8 JSON 请求，stdout 只写一个 JSON 响应，日志写 stderr，退出非零即失败。评测进程不 import 被测业务模块；`--module` 是受信任宿主 shim 的入口，实际 CLI/模型应由 shim 调用。HTTP 适配器向指定评测 shim POST 同一协议，不直接假设现有 `/api/v1` 已实现此入口。

每个请求是独立 Case 沙箱的一组顺序操作，步骤从 0 开始。每个场景都使用新 run_id 和空输出目录。三次重试在同一请求中，使用相同幂等键；内容变化复用键应返回 409。不同场景之间不共享运行状态。

`request` 包含 `protocol, run_id, case_id, workspace, inputs, operations, instruction, host`。`inputs` 是当前场景授权的来源清单，字段为 `id/version/case_id/name/role/sha256/path`。`workspace` 下只暂存本场景业务文件。期望值、场景标签、覆盖说明、其他 Case 正文、`test/cases`、`test/expected` 和 `core15` 后续确认邮件不进入请求。

E02a 和 E02b 是两个隔离快照：缺价请求中根本不包含补价文件，后续补价快照才提供补价来源。这验证证据边界，尚不等于真实 Worker 的跨会话恢复测试。

金额参数 `quantity/fx/margin` 是业务计算条件，margin 使用小数比例；供应商成本必须从指定 `source` 的实际文件提取。不要把未选中的较新来源替代固定版本。`quote_change` 在缺少新包装价格时应阻断。`approve_sample` 只允许宿主授权和证据范围内的批准；本套件未授予任何正式审批、外发或生产放行权限。

## 响应和实际文件

响应包含 `protocol/run_id/case_id/execution/steps/events`，`steps` 与请求操作一一对应。执行类型只能如实报告 `offline` 或 `real_model`；没有真实模型调用时不得报告后者。

报价步骤返回：

```json
{
  "status": "draft",
  "quote": {"unit_usd": "8.69", "total_usd": "26070.00", "quantity": 3000},
  "artifact": {"id": "quotation-v1", "version": 1, "path": "outputs/quotation-v1.json", "sha256": "64位小写十六进制", "bytes": 123},
  "citations": [{"source": {"id": "factory-a", "version": 1}, "sha256": "输入原字节哈希", "field": "cost_cny", "locator": {"type": "xlsx", "sheet": "Factory A Quote", "cell": "B13"}, "excerpt": "50"}]
}
```

示例哈希和 bytes 是占位解释，不能作为有效响应。实际 JSON 成果文件必须包含 `case_id/version/status/quote/cost_cny/citations/base_id/base_sha256`。`cost_cny` 属于内部核算成果，不能进入客户包；客户包从明确的公开字段白名单生成。新版本引用旧成果的 id 和字节哈希。旧版下载必须返回原文件和哈希。客户端声称的哈希不够：评测程序重新读取文件、计算 SHA-256，并解析内容验证数值。

来源定位支持三类：

- `text`: `start/end` 为 UTF-8 解码后 Unicode 字符索引，左闭右开；摘录必须逐字匹配。传输的输入哈希始终基于原字节。
- `xlsx`: 工作表名及单元格地址，读取实际 OOXML 值/公式缓存；不根据文件名推断数值。
- `pdf`: 从 1 开始的页码与实际页面文字 `quote`，使用 pypdf 提取；缺解析器时 blocked。

报价必须逐件向上取整到美元美分，再乘数量。评测端使用有理数算法，离线替身使用 Decimal，以避免共用定价函数导致自证。

`export` 返回 `exports: [{format, audience, path, sha256, bytes}]` 和 `errors: [{format, code}]`。注入 `faults.export_fail=["pdf"]` 时 HTML 仍应保留，PDF 出错须报告 `partial` 和失败事件。新建成功记录却没有实际文件不算成功。客户 ZIP 递归检查成员及嵌套 ZIP；未知或不可解析成员使检查失败，不默认安全。导出文字检查不能代替文件渲染和人工视觉验收。

缺价返回 `status=blocked, quote=null, reason=MISSING_COST`；跨 Case 返回 `denied, http_status=403/404`，不携带正文；幂等冲突返回 `conflict, http_status=409, reason=IDEMPOTENCY_CONFLICT`；未连接邮件工具返回 `blocked, sent_at=null, reason=CONNECTOR_UNAVAILABLE`。

## 执行事件

每个事件包含递增且连续的 `seq`、`run_id`、`step`、`type`。运行起止事件 step 为 null。顺序为 `run_started → 各步骤 operation_started/工具事件/operation_finished → run_finished`。

`run_started.request_sha256` 使用 `inspection.canonical` 的字节哈希：键排序、无多余空白、UTF-8、非 ASCII 不转义、不接受 NaN。文件读取事件 `file_read` 绑定 source 的 id/version、原字节 sha256 和 bytes；写入事件 `artifact_written` 绑定 artifact_id、path、sha256、idempotency_key。导出对应 `export_ready` 或 `export_failed`；重复返回对应 `idempotency_replay`；拒绝访问对应 `access_denied`。

真实模型模式还需 `model_call` 记录 provider、model、request_id、input_sha256、output_sha256；正式接入时应附计费/追踪日志和宿主 Run/Worker 事件做独立核对。适配器自报事件只证明协议可检查，不能证明模型调用真实发生。报告会标为 `reported_unverified`，不会据此给整个产品通过结论。

## HTTP 传输

HTTP 请求将 workspace 替换为 `.`，每个 input 增加 `data_base64`。服务端必须先验证来源 sha256，以独立临时目录落盘；`run_started` 必须绑定**原始 wire 请求**的 canonical 哈希，不能绑定重写本地路径后的请求。响应额外返回 `output_files: [{path, data_base64}]`；每条相对路径只能位于 outputs/，不能重复。评测端落盘后再次核对引用的大小、哈希及内容。响应上限 20 MB。

测试里的本地 HTTP 服务只是协议回环替身，没有验证实际后端登录、Case 权限、工具注册或 Worker。接入真实服务时应由 shim 将 `host` 约束映射到认证会话；不能把用户输入中的 actor、批准字段或 source id 当成授权。成本原件、scope 批准和不可变版本都由宿主执行边界保护。

E05 当前仅向被测端提供外 Case 的不透明引用，正文由评测宿主保管；真实权限验收还必须通过受信任的 setup 将该来源入库另一 Case，再用当前 Case 会话访问。返回未知 ID 的 404 不能单独证明真实 ACL 已验收。`faults` 同样是 shim/宿主的故障注入控制，应在真实导出调用处注入失败，不把标准答案或故障预期放进模型 Prompt。

## 与主执行链映射（待冻结）

| 评测字段 | 未来主链路对象 | 接入要求 |
| --- | --- | --- |
| case_id + run_id + host | ExecutionContext | 认证宿主注入；不信任 Prompt 自授权限 |
| inputs.id/version/sha256 | FileRef | 固定原始版本；不按同名文件静默替换 |
| citations.source/locator | Citation | 保留页码、sheet/cell、原字节哈希 |
| steps.status/reason/artifact | ToolResult | 区分失败/部分成功/阻断；不得只回成功文案 |
| events | 工具/Run/Worker 日志 | 同一 run 和幂等键；独立核对外部日志 |

尚无已提交 agent-kit 协议可在本基线上核对。兼容性结论只覆盖本协议的 module、stdio、HTTP 回环；主链路仍 blocked。接入后需要实际工具输出与数据库/版本/授权证据，不允许用本离线适配器替代主链路验收。
