# BOM 图片候选识别

独立函数、CLI、产品能力声明和薄适配层已实现。**真实视觉识别未验收；主链路未接入。** 本模块只产生待复核候选、缺失项和疑问，不批准供应商价格，也不复刻报价计算器。

## 支持范围

输入为单张清晰印刷 BOM 表格的 PNG/JPEG，最多 10 MiB、2500 万像素；实际解码检查，不以文件扩展名判断。动画 PNG、PDF、多页拼接、手写、复杂合并表头不在本轮保证范围内。模型需支持图像输入，只有文本能力的 `MODEL_NAME` 不能完成本功能。

候选字段：材料名称、规格、用量、单位、单价、币种、行小计，以及原表合计/币种。缺失值为 `null`；不补算原表未写的价格或小计。原图引用完整保存在 `source.file_ref`，另计算文件字节 SHA-256。`recognition.raw_response`、原始转录、`original_extraction` 和每行 `source.line/raw_text` 保留证据。行号是模型观察到的视觉数据行号，仍需人工核对；不声称可靠像素坐标。修正后的值与原图证据分开保留。

每次输出均为 `status=candidate`、`needs_review=true`、`price_approved=false`，即使没有算术问题也不表示识别正确或商业批准。`validation.has_questions=false` 只代表确定性规则未发现问题。

## 安装与运行

从仓库根目录进入本模块，使用 Python 3.12+：

```powershell
Set-Location extensions/bom-vision
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

默认沿用 `backend/app/agent.py:109-112` 的 `MODEL_NAME` 和 `MODEL_API_KEY`。端点优先级为显式构造参数、`OPENAI_API_BASE`、`OPENAI_BASE_URL`、`https://api.openai.com/v1`，与现有 ChatOpenAI 的环境端点优先级一致。超时默认 25 秒。不读取任何 `.env` 文件，不打印配置或密钥；由调用进程安全注入环境。没有模型配置时返回明确 `blocked`，不降级为假识别或文字规则。

```powershell
# 预先在当前运行环境提供 MODEL_NAME / MODEL_API_KEY 和可选端点，不把密钥写进命令历史。
.venv/Scripts/python.exe -m bom_vision recognize samples/clear.jpg --out out/candidate.json
.venv/Scripts/python.exe -m bom_vision validate out/candidate.json --out out/revalidated.json
.venv/Scripts/python.exe -m bom_vision correct out/candidate.json samples/patches.example.json --expected-revision 1 --actor local-reviewer --reason '核对原图数字' --out out/corrected.json
.venv/Scripts/python.exe -m scripts.accept_live
```

`--out` 拒绝覆盖已有文件；重跑使用新文件名。退出码：CLI 成功为 0，缺配置/无效输入/版本冲突/请求失败为 2；有疑问的合法候选仍成功输出。真实验收脚本成功为 0，观察不符合预期为 1，依赖阻塞为 2。`out/` 在模块内被忽略。

`recognize --file-ref path/to/versioned-ref.json` 可以保留调用者提供的原始 FileRef 对象；省略时只生成本机文件 URI，标记 `local-cli-only`。CLI 不具备 Case 授权或业务落库能力，不能直接作为服务端工具执行；本机 URI 也不能冒充业务资产版本。

## 函数与纠正接口

```python
from bom_vision import recognize, correct, revalidate
from bom_vision.adapters import OpenAICompatibleAdapter

# image_bytes 与 original_file_ref 应来自已授权的不可变文件版本。
candidate = recognize(image_bytes, original_file_ref,
                      OpenAICompatibleAdapter.from_environment())
edited = correct(candidate, [
    {"row_id": "row-1", "field": "quantity", "value": "3.50"},
], expected_revision=1, actor="authenticated-reviewer-id", reason="核对原图")
checked = revalidate(edited)
```

数字字段以字符串或 null 传入，避免浮点误差；`2,50`、`1,000`、指数、非有限数、超过 15 位整数/8 位小数均保留为疑问，禁止猜测地区数字格式。标准小数用 `.`。单位有保守白名单，陌生单位与带计价基数的单位要求核对，不自动换算。币种校验三位大写代码格式，不推测 `¥` 或 `$` 的含义，不自动汇率换算。金额用 Decimal 比较用量×单价与行小计、同币种原行小计之和与原表合计，固定绝对容差 0.01；税费、折扣及复杂计价规则可能触发需解释的冲突。缺少小计或币种时明确提示总额不可比较。

纠正采用原子 patch 列表，必须提供当前 revision、actor、reason。可改行字段，或用 `row_id=null` 改表合计/币种；不可修改证据、状态或批准字段。成功递增 revision，并记录 before/after；行字段纠正会清除该字段原有不确定标记，再全量校验。原始转录、识别 notes、来源哈希保持不变。notes 中原有识别疑问仍保留，供复核追踪。纯函数的版本校验不能替代数据库并发控制，actor 也必须由宿主从认证上下文注入。

`VisionAdapter` 只要求 `name` 和 `extract(image_bytes, mime_type)->str`。自定义适配器可替换默认 VLM；严格输出结构见 `bom_vision/adapters.py` 的 `PROMPT` 以及 `samples/*.fake.json`。模型输出必须携带行原文与正整数视觉行号，禁止缺证据的行。原图文字按不可信数据处理；所有结果仍须人工复核。

默认适配器把实际图片字节编码为 data URL，调用 `/chat/completions`，不发送本地路径；拒绝截断、空内容、非法 JSON/结构、远程 HTTP 明文端点和重定向，不输出远端错误响应。没有自动重试、持久化缓存、后台任务或工具调用。图片和转录属于业务证据，部署时由宿主管理存储、访问和留存。

## 主链路适配边界

`bom_vision/integration.py` 的 `HostPorts` 是本目录内临时依赖注入接口，不是新的共享协议，也不实现同名 ExecutionContext/FileRef/Citation/ToolResult。

宿主提供 `authorize_file(context, ref)`、`read_file(context, ref)`、`make_citation(context, ref, sha256, locator)`、`make_result(context, data=..., citations=...)`。调用顺序严格为授权→原版本读取→识别→Citation→ToolResult；BOM 专用字段全部在 `data` 中。每个调用收到相同内容的分离引用，避免端口意外修改引用后读错版本。拒绝授权后不会读取或调用模型。

缺失 context/ref、任一端口或模型时返回本地诊断 `status=blocked`。这些诊断字典不能当成共享 ToolResult；集成者应映射到正式失败结果。宿主必须校验 Case、文件资产/版本及内容摘要、读权限和模型外发策略，确保读取正是已授权的不可变版本。只检查 Python 对象存在不能代替这些保证。

本基线没有未提交的 agent-kit。本模块未复制它，也未注册工具、改 Worker、绕过授权/版本/批准。后续由「实现 Agent 文件工具闭环」统一接入真实公共类型、工具注册、文件解析器、候选持久化及前端纠正入口。批准、报价采用、成果版本和审计门禁仍由主模块负责。

## 样本与验收

`samples/` 全为本模块生成的合成素材，无客户资料。`generate_samples.py` 把文字绘制进像素，不依赖隐藏文本元数据；需 Pillow 与可用 DejaVuSans.ttf。已提交图片及 manifest，不要求运行测试前重新生成。

| 样本 | 视觉内容/预期 |
| --- | --- |
| `clear.jpg` | Nylon 600D，2.50 m × 12.00 CNY = 30.00；Zipper 4 pcs × 1.50 = 6.00；合计 36.00 |
| `missing_price.png` | 第一行单价、小计留白；不根据合计反推 |
| `blurry_digit.png` | 第一行用量区域实际高斯模糊；应输出缺失/不确定 |
| `total_conflict.png` | 行小计仍为 30.00 + 6.00，原表合计改为 39.00 |
| `changed_number.png` | 图片中用量实际改成 3.50，小计 42.00，合计 48.00 |

离线测试使用显式 `FAKE-replay-not-vision` 适配器，响应与图片 SHA-256 绑定；错图会失败。另验证发送给模型的 base64 解码后等于实际图片字节，数字变更图会发送不同请求。**这些测试仅证明管线、校验和证据行为，不证明模型读图准确率。**

`scripts.accept_live` 仅调用真实适配器，不读取假响应。它运行全部五种样本，检查关键字段、缺价保留、模糊数字不确定、合计冲突及实际改图后的结果变化；原始结果写入 `out/live/`，控制台只输出验收摘要。通过该合成样本集也不代表所有生产 BOM 的识别质量，应继续用授权业务样本评估。

本轮实际验证（2026-10-31）：Python 3.12.14、Pillow 13.0.0，21 项 unittest 通过；人工查看了模糊数字图片。真实验收脚本已执行，返回 `vision_model_not_configured`（脚本退出码 2），无真实模型请求完成，**真实识别未验收**。没有执行不相关后端/前端全量测试，未改其代码。

## 文档核验与交付

Context7 MCP 在本轮工具列表不可用。实现前使用 OpenAI Docs 核验了 [官方 Images and vision 文档](https://developers.openai.com/api/docs/guides/images-vision?api-mode=chat) 的图片 data URL 请求格式，并核验 [LangChain 官方端点配置优先级](https://reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/openai_api_base)。仓库真实配置来自只读检查 `backend/app/agent.py` 与 `.env.example`，未打开密钥文件。

能力机读声明见 `capability.json`。独立实现可运行，真实模型验收因缺配置阻塞；主链路接入仍依赖主模块文件工具与 agent-kit。所有新增代码、样本、测试和文档仅位于 `extensions/bom-vision/`，不合入 `justike`。
