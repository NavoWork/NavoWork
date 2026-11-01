# 通用演示 Mock

`demo_mock` 提供通用的“命名输入→精确匹配场景→预置 JSON”封装。它与 BOM、Pillow、Agent、模型配置和业务批准无关。当前为遵守目录独占约束，代码放在本扩展内；没有新增仓库共享协议。其他流程可以导入同一 Python 包，用自己的场景清单和业务输出结构，不必复制匹配代码。

## 运行 BOM 演示

在 `extensions/bom-vision` 目录执行，Python 3.12+，安装方法沿用 README；原先已安装 editable 包的环境需重新 `pip install -e .` 才能注册新增控制台命令。

```powershell
python -m bom_vision.mock_cli samples/clear.jpg --catalog samples/mock.catalog.json --out out/bom-demo.json
python -m bom_vision validate out/bom-demo.json
python -m bom_vision correct out/bom-demo.json samples/patches.example.json --expected-revision 1 --actor demo-user --reason '演示纠正' --out out/bom-demo-corrected.json
```

`bom-mock` 是安装后同一入口的短命令；`bom-vision` 及原真实识别实现保持原样。mock 入口不调用模型、不读取模型环境变量，也不通过 Agent/Worker。未知图片返回 `mock_sample_not_found`，没有真实识别回退。

`samples/mock.catalog.json` 直接引用现有五个 `*.fake.json`，不另造候选数据。`mock_recognize` 将命中内容通过一个私有静态适配器传入原来的 `recognize`，继续做图片解码、原 FileRef/哈希保留、原文定位及 Decimal 校验。原 `correct`、`revalidate` 无需改动，mock 标记和场景信息在纠正后仍保留。

服务端普通函数调用：

```python
from demo_mock import Catalog
from bom_vision.mock import mock_recognize
from bom_vision import correct

# catalog 为应用启动时配置的演示资产；不要由上传请求指定路径。
catalog = Catalog.load("/configured/demo-assets/mock.catalog.json")
# image_bytes 和 file_ref 来自宿主已授权的同一文件版本。
candidate = mock_recognize(image_bytes, file_ref, catalog=catalog)
edited = correct(candidate, patches, expected_revision=1,
                 actor=authenticated_user_id, reason="核对演示图")
```

运行时只传已读取的字节与原文件引用。原文件引用在运行时附加，绝不从 fixture 复制某个旧 Case 的资产。图片来源摘要与静态 fixture 摘要分别保留。mock 匹配不承担 Case 读权限、真实版本校验、持久化或批准；普通后端入口沿用现有宿主权限。这不要求 Agent 来执行工作流。

## 为其他流程准备场景

1. 选一个 `workflow` 名称及其步骤 `operation`，例如 `document-demo / summarize`。
2. 准备输入文件或 JSON，以及自己业务结构的输出 JSON。
3. 用 `add` 注册指纹及输出路径，后续直接 `run` 或调用 `Catalog.replay`。

本模块附带一个可运行的纯 JSON 两步示例：

```powershell
python -m demo_mock check --catalog examples/document-demo/catalog.json
python -m demo_mock run --catalog examples/document-demo/catalog.json --workflow document-demo --operation summarize --json request=examples/document-demo/request.json
python -m demo_mock run --catalog examples/document-demo/catalog.json --workflow document-demo --operation next-actions --json summary=examples/document-demo/summary.json
```

应用内串联步骤，不需要流程框架：

```python
from demo_mock import Catalog

catalog = Catalog.load("examples/document-demo/catalog.json")
first = catalog.replay("document-demo", "summarize", {
    "request": {"language": "zh", "document_type": "specification"},
})
second = catalog.replay("document-demo", "next-actions", {"summary": first["data"]})
```

步骤可以任意命名；结果 `data` 支持任意标准 JSON。通用层不认识业务字段，后续流程的校验由业务适配函数调用已有逻辑。每步都无状态且要求输入精确匹配，没有随机延迟、后台动作或自动外发。若业务需要按阶段区分，同一个输入也可以通过不同 `operation` 或显式 JSON 输入字段区分。

新增自己的场景，例如先把 `request.json` 和 `response.json` 放进 `out/my-demo/`：

```powershell
python -m demo_mock add --catalog out/my-demo/catalog.json --catalog-id my-demo-v1 --scenario preview-one --workflow my-demo --operation preview --json request=out/my-demo/request.json --output out/my-demo/response.json
python -m demo_mock run --catalog out/my-demo/catalog.json --workflow my-demo --operation preview --json request=out/my-demo/request.json --out out/my-demo/result.json
```

文件输入用 `--file image=path/to/image.png`，JSON 输入用 `--json request=path/to/request.json`；可重复且可混合使用，但输入名称不能重复。`add` 计算全部指纹、校验输出 JSON，在原清单追加场景并原子替换文件；不会复制素材或覆写 fixture。作者命令按单人串行使用，不提供多写者并发控制。`run`/函数重放始终只读，`--out` 拒绝覆盖已有文件。

`python -m demo_mock fingerprint --file image=samples/clear.jpg` 可单独查看指纹；`check --catalog ...` 会校验整个清单的结构、重复匹配及全部 fixture 的摘要/JSON。

## 匹配规则与结果

索引由 **workflow + operation + 完整命名输入集合** 构成；输入名也参与匹配，缺字段、多字段或值变化都不会误命中。场景 ID 用于结果溯源，不能用它跳过输入校验。冲突的场景 ID 或相同匹配键会使清单加载失败，避免依赖先后顺序。

- `bytes`：对完整原始文件字节计算 SHA-256；文件名不参与匹配。截图、重新压缩、元数据改动都会改变指纹；需要多个版本时逐个登记，没有相似图片匹配。
- `json-v1`：字符串键排序、紧凑分隔符、保留 Unicode、UTF-8 编码后计算 SHA-256。对象键顺序和输入文件格式不影响匹配；列表顺序、类型及具体值参与匹配。不做 Unicode 归一化或数字语义归一化，`1` 与 `1.0` 区别对待。这是本封装的 Python JSON 规则，不声称 RFC 8785 跨语言标准。
- 输出 fixture 也固定 `json-v1` 摘要；换行、缩进或键顺序变化仍可用，业务值变化会报 `mock_output_hash_mismatch`。正式修改输出时更新清单摘要/版本，不会悄悄改演示结果。

通用结果为 `{"mode":"mock","mock":{...},"data":...}`，mock 元数据包含 catalog ID、场景 ID、工作流/步骤、输入摘要及 `output_json_sha256`。BOM 入口继续返回原候选结构，仅增加同样的 `mode`/`mock` 字段。`recognition.adapter` 为 `mock-fixture-replay`，其中 raw_response 是静态 fixture 序列化文本，绝不表示模型识别。每次重放产生独立结果对象，纠正不会改预置文件或后续重放。

输入文件最大 10 MiB，JSON/清单/输出文件最大 2 MiB，最多 1000 个场景、每场景 32 个输入，JSON 最深 50 层。拒绝重复 JSON 键、NaN/Infinity 及非标准 JSON 对象。fixture 路径必须位于清单所在目录内；路径也会在读取前重新解析，拒绝跳出目录的链接。清单和素材应由演示作者维护，运行时不接受用户提供的任意路径。

所有 CLI 成功退出 0，未匹配/资产损坏/重复规则/无效输入退出 2，并输出带 `mode=mock` 的稳定错误码；不会把输入正文或本地路径附在错误中。无匹配必须在页面提示“未匹配预置演示样本”。延迟动画、进度展示由 UI 决定，结果仍应清楚标记为 mock。

## 验证与接入状态

2026-10-31 实测：原有 21 项测试继续通过；新增 14 项 mock 测试通过，覆盖全部五张 BOM 图、未知/改动输入、多步骤 JSON、混合输入、场景冲突、输出篡改、运行时引用隔离、纠正复用以及 CLI 场景登记/重放。测试主动拦截网络和模型配置访问，BOM mock 仍成功。

```powershell
python -m unittest discover -s tests -v
python -m scripts.check_agent_kit --revision d23ab0a
```

默认独立测试为 **35 passed / 3 skipped**；跳过的是未安装 agent-kit 时的公共协议检查。第二个命令仅用 `git show` 从已提交 `d23ab0a9ecba4dffd4ce0aa97bd496bf668aa156` 将真实 contracts 包读入临时目录，三项兼容测试另行全部通过；没有合并主分支、修改共享协议或读取未提交文件。验证了真实 ExecutionContext/FileRef/Citation/ToolResult 构造与序列化、授权拒绝时不读文件，以及 JSON 指纹与公共 digest 对齐。

公共 ToolResult 没有顶层 citations 字段；宿主应将候选和 Citation 序列化内容放在 `data`，状态可用 `needs_review`。独立 mock 函数已经可供普通后端使用；工作台上传路由、结果落库、页面标识、扩展注册仍由主模块统一接入。本轮未新增 HTTP 路由或前端入口。真实视觉能力保留但不再是 mock 演示验收条件，也未宣称完成真实识别。

Context7 入口不可用。本次未增加第三方依赖，核验了 Python 官方 [hashlib](https://docs.python.org/3/library/hashlib.html) 与 [json](https://docs.python.org/3/library/json.html) 文档。将来需要迁到公共 demo 包时，可以整体迁移 `demo_mock/`，无需改变场景清单或 BOM 校验逻辑。
