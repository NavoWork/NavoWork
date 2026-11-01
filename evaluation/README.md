# 独立 Agent 验收入口

只修改和提交 `evaluation/`。基线为 `4e34ce0958912fc3326358589a520cbf38c5103e`，含 `5fcf0a1`；分支 `codex/agent-evaluation`。本目录不依赖后台启动、不改项目依赖、不导入未提交的 agent-kit。

本套件验收评测器自身和适配器输出。**离线通过不代表真实 Agent、整个后端或产品通过。** 未指定运行时默认输出 blocked；视觉检查始终单独报告，当前未执行。模型调用记录仍需与宿主日志独立核对。

## 运行

在仓库根目录运行。Python 3.12+；标准库覆盖核心逻辑和 XLSX 读取，PDF 来源解析额外使用已有 pypdf。未安装时该场景 blocked。Bundled Python 当前已提供 pypdf，不安装或修改根依赖。

```powershell
$evalPython = 'C:/Users/Justike/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $evalPython -m evaluation list
& $evalPython -m evaluation self-test
& $evalPython -m unittest discover -s evaluation/tests -v
& $evalPython -m evaluation run --adapter reference --seed 7319
& $evalPython -m evaluation run
& $evalPython -m evaluation backend-probe
& $evalPython -m evaluation compat-check --revision d23ab0a
```

`run` 未配置 runtime 时退出 2；存在场景失败退出 1；全部场景检查通过退出 0。这个退出码只针对离线/适配器场景，不代表产品发布批准。外部素材声明哈希审计独立记录在 `declared_fixture_integrity`，即使离线场景通过也不能忽略其失败。报告的 `product_acceptance` 明确保持 `not_accepted`。

默认输出到 `evaluation/runs/<时间戳>/`，包含 `report.json`、简明 `failures.txt`，逐场景 public request/wire-request/response、实际输入副本和输出文件。目录已存在时拒绝覆盖。所有输出必须位于 evaluation/；运行目录不提交。固定 seed 可重建变体，UUID/时间戳及 ZIP 容器元数据允许不同，来源/成果实际字节哈希保留在每次报告。

## 接入 CLI、模块或服务

```powershell
& $evalPython -m evaluation run --adapter module --module evaluation.reference_adapter:run
$evalCommand = @($evalPython, "$((Get-Location).Path)/evaluation/stdio_adapter.py") | ConvertTo-Json -Compress
& $evalPython -m evaluation run --adapter command --command-json $evalCommand
& $evalPython -m evaluation run --adapter http --endpoint http://127.0.0.1:8000/evaluation/run --token-env EVAL_SERVICE_TOKEN --mode real-model
```

前两个示例仍然调用**离线替身**。第三条要求服务端实现 [PROTOCOL.md](PROTOCOL.md)，当前仓库后端没有这个评测入口。HTTP 连接错误是失败，不会回退成离线通过。`--timeout` 默认为 30 秒，上限 55 秒；`--scenario E03 --scenario E09` 可做兼容性子集。不得把测试资料包、expected 或评测解释文档整体上传给被测 Agent。

module/command 是受信任适配器入口，不是 OS 沙箱：同一账号的子进程仍有宿主文件系统权限，环境变量也会继承。对可主动访问文件系统的真实 Agent，宿主须额外隔离工作目录、限制文件工具权限并禁止读取 `evaluation/`、`test/cases`、`test/expected`；HTTP 只传授权文件的字节。评测请求本身绝不包含 oracle，且不会复制 oracle 到场景目录。

## 覆盖与故障验证

| 场景 | 检查 |
| --- | --- |
| E01 | 原 XLSX A / PDF B，金额、单元格/页码定位；无尺寸图不生成尺寸/材质等级承诺 |
| E02a / E02b | 缺彩盒价格阻断；后续补价快照计算；补价不进入早期上下文 |
| E03 | 同名不同内容、固定版本、新数值/数量/汇率/毛利变体 |
| E04 | 假设价格不能成事实；条件与否定不能扩大为样品批准 |
| E05 | 跨 Case 拒绝，无敏感正文；外 Case 字节不进入被测工作区 |
| E06 / E12 | 三次同键仅一次写入；不同内容复用键返回 409 |
| E07 | 旧版下载哈希保持、新版 base id/hash 正确 |
| E08 | 客户 HTML/ZIP 内容检查，包括压缩包内部原件成本泄露 |
| E09 | PDF 故障注入，HTML 保留，partial + 失败事件准确 |
| E10 / E11 | 未连接邮件禁止“已发送”；恶意附件不授权操作 |

`self-test` 运行正确对照和 13 类缺陷适配器，每种缺陷必须命中指定的不变量；仅因异常退出或其他无关检查失败不算检出。四个关键类别为金额、旧内容、伪成功、客户成本泄露；其余覆盖缺价乱填、批准越权、跨 Case 泄露、重复写入、覆盖旧版、虚假来源定位、文件哈希、事件遗漏和幂等冲突。测试还验证来源/成果篡改、路径越界、超时、损坏响应、嵌套 ZIP 以及 module/stdio/HTTP 兼容。

来源 hash 绑定原字节，评测端独立读取业务文件和实际生成文件，不采用被测 Agent 自评分。金额 oracle 用有理数计算，适配器用 Decimal。源定位支持 text 字符范围、XLSX 工作表/单元格、PDF 页码摘录。图片仅验证未知字段策略，本次没有任何视觉内容识别结论。

## 报告、阶段与已知边界

机器报告 schema `navowork-eval-report/1` 包括时间、HEAD、seed、模拟标记、实际输入清单/来源哈希、请求/响应哈希、执行事件计数、实际输出哈希、逐条失败、离线/真实模型/文件内容/文件视觉层、独立能力与主链路阶段。当前结果见 [DELIVERY.md](DELIVERY.md) 和 `reports/`。

第一阶段：独立 CLI、评测协议、文件检查器、故障变异、传输兼容性已实现。第二阶段已针对随后提供的已提交 `d23ab0a` 做 11 项实际协议/本地工具兼容检查，全部通过；包括实际定价/文件生成、客户 ZIP、导出故障与恢复、版本/CAS、外 Case 已存在来源及宿主权限/代次栅栏。`compat-check` 只从指定 commit 的 Git 对象提取代码到忽略的 evaluation/runs，不读取其他 checkout 的未提交文件，也不合并其分支。真实模型、后端 Worker、认证会话、持久化批准及浏览器路径仍 blocked；详见 [兼容报告](reports/agentkit-compatibility.json)。

`backend-probe` 从本 worktree 已提交后端源码 AST 仅提取指定函数，使用内存替身调用；会记录源码哈希和行号。它不启动后端、不访问业务数据库、不发模型请求，结果不能升级成真实服务复现。报告区分已观察的函数行为与未测的客户包/伪成功路径。

基线素材校验器目前失败：5 份早期 PDF 与 3 封 core15 历史副本声明 SHA-256 不符。5 份 PDF 转 LF 后与声明相符，且 Git 显示 `i/lf w/crlf`、`core.autocrlf=true`；这里只做诊断，不改素材、不更改 `.gitattributes`，也不重新 seal。三个历史 EML 副本同样存在差异，但简单 LF 归一化不能与原声明哈希一致。具体 raw hash 见报告；core15 正文未进入被测场景。

本会话无 Context7 MCP 入口，已查阅 Python 官方 [subprocess](https://docs.python.org/3.12/library/subprocess.html) 与 [urllib.request](https://docs.python.org/3.12/library/urllib.request.html) 文档。实现采用无 shell 的 argv、stdin JSON、退出码/超时检查以及显式 HTTP JSON 请求。
