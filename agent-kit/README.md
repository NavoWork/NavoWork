# NavoWork Agent Kit

独立的 Case 文件工具与报价 Agent。代码基于 `justike` 合入 `origin/lirui@5fcf0a1` 后开发。当前模块提供本地执行和测试入口；工作台复用其中受控文件工具，并保留 guilimao 原生业务工具链；宿主接入状态见 `docs/host-mapping.md`，不能将 CLI 回放视为工作台集成验收。

## 安装与验证

Python 3.12+，建议独立虚拟环境。在仓库根目录执行：

```powershell
python -m venv agent-kit/.venv
& agent-kit/.venv/Scripts/python.exe -m pip install -e './agent-kit[test]'
& agent-kit/.venv/Scripts/python.exe -m pytest agent-kit/tests -q
& agent-kit/.venv/Scripts/python.exe agent-kit/scripts/replay.py --output agent-kit/output/my-replay
```

本次验证使用 Codex bundled Python，依赖安装在忽略的 `agent-kit/.deps/`，没有改写 bundled runtime：

```powershell
$py = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = 'agent-kit/src;agent-kit/.deps;agent-kit/tests'
& $py -m pytest agent-kit/tests -q
& $py agent-kit/scripts/replay.py --output agent-kit/output/new-replay
```

第二种方式适用于本开发环境；新环境使用上方正式安装方式。`replay.py` 默认创建临时目录，仅显式 `--output` 时保留到指定目录；目录必须没有已有回放，避免覆盖证据。输入只读复用 `test/inputs/`。测试、回放脚本可读取 oracle；产品包和模型上下文都不会读取 `test/expected/`、`test/cases/` 或 `test/core15/`。

## 真实 Agent

`MODEL_API_KEY`、`MODEL_NAME` 必须由环境配置，可选 `MODEL_BASE_URL`。密钥不传入 Prompt，不保存到事件或交付包。模型调用使用 LangChain `bind_tools`；LangGraph 保存调用和工具回传，`interrupt` / `Command(resume=...)` 在同一 Case/Job 线程等待和继续。产品没有固定的业务执行脚本。

```powershell
navowork-agent init --workspace ./agent-kit/output/live-case --case BAG-2026-DE-001
navowork-agent import --workspace ./agent-kit/output/live-case --files ./test/inputs/BAG-2026-DE-001/inquiry.eml ./test/inputs/BAG-2026-DE-001/factory-A-quote.xlsx ./test/inputs/BAG-2026-DE-001/factory-B-quote.pdf
```

准备一个仅包含用户已确认依据的 JSON 文件，例如 `{"fx":"7.20","margin":"0.20"}`，通过宿主接口录入：

```powershell
navowork-agent facts --workspace ./agent-kit/output/live-case --facts-json ./user-decisions.json
navowork-agent run --workspace ./agent-kit/output/live-case --goal '查阅附件，使用已确认汇率和毛利核价，生成并校验规格、成本和客户报价草稿' --output ./agent-kit/output/live-exports
navowork-agent import --workspace ./agent-kit/output/live-case --files ./test/inputs/BAG-2026-DE-001/change-color-box.eml
navowork-agent run --workspace ./agent-kit/output/live-case --goal '按客户邮件修改包装；缺少新价格时先完成规格草稿并提问'
navowork-agent import --workspace ./agent-kit/output/live-case --files ./test/inputs/BAG-2026-DE-001/factory-A-color-box-update.eml
navowork-agent run --workspace ./agent-kit/output/live-case --resume '工厂补价邮件已加入，请继续同一目标并刷新关联文件'
```

本开发环境可用 `& ./agent-kit/scripts/run.ps1 ...` 替代安装后的 `navowork-agent`。缺模型配置时明确返回 `MODEL_NOT_CONFIGURED`、`live_executed:false` 和非零退出码。`tests/live/` 的真实模型测试会跳过，离线替身无法替代。执行步数默认 30，单次模型请求超时 30 秒、最多重试 1 次，尝试预算 180 秒，在模型/工具边界检查；不声称能强制终止任意同步库调用。文件读写受大小和结构限额约束。

## 暴露的工具

`list_context`、`read_document`、`load_skill`、`list_artifacts`、`calculate_quote`、`publish_documents`、`prepare_pi`、`create_working_copy`、`edit_file`、`validate_artifact`、`export_artifact`、`package_customer_files`、`request_info`。参数 JSON Schema 来自严格 Pydantic 模型，拒绝未知顶层参数。权限上下文、物理路径、已确认用户依据和测试故障注入都不能由工具参数设置。没有 shell、任意 Python、外发、批准或收款工具。

四个产品 Skill 随包保存在 `src/navowork_agent/skills/`，由工具按需加载，不安装个人 Codex skills。DOCX/XLSX 来源须先复制为独立工作副本，工具保留原件并对副本生成新版本。模型负责语义映射、判断假设/否定与选择工具，程序负责确定性计算、访问和版本检查。测试中由脚本构建快照的流程明确属于离线工具回放。

报价使用 Decimal，数量为严格正整数，成本项明确范围 `per_unit` / `per_order`；base、packaging、local 任一缺失都不补零。FX 为 CNY/USD，毛利是 `[0,1)` 的比例；按单件向上舍入 USD 0.01 再乘数量。每个已知字段需要来源定位或完全匹配的宿主用户依据。引用检查能核验哈希、定位和摘录存在，不能自动证明模型的语义解释正确；后者需要真实模型与外部评测。

## 文件与版本

- 读取 UTF-8 TXT、正确解码的 EML、文字 PDF、基础 XLSX 和 DOCX；返回页码、表名/单元格、段落/表格定位。图片和扫描件不由该文本读取器 OCR；工作台另通过 BOM vision 扩展生成待复核候选。
- 从同一受控快照制作规格 DOCX、内部成本 XLSX、客户报价 XLSX/PDF。缺价仍生成非价格草稿；报价状态为 Pending pricing，金额 Unknown。
- XLSX 只重算同表相对 A1 引用、四则运算、SUM、ROUND、ROUNDUP；不支持绝对引用、跨表、外链和其他函数。缓存写回 OOXML 后重新打开检查，并核对报价金额。编辑支持单元格和无公式工作簿的空行/列插入；不会伪装支持任意公式引用平移。
- DOCX 编辑支持段落、表格单元格和受控图片引用。任意字段手改会标记需要内容协调并阻止自动覆盖；追加的规格备注进入快照，在下次生成时保留。复杂排版和任意 Office 特性不在范围内。
- 来源永不覆盖；输出是不可变版本，基线采用 CAS。幂等键按 Case/Job 隔离，绑定规范化参数及引用；同键不同请求为冲突。旧上下文 generation 的迟到写入拒绝。
- 单一导出分支失败不回滚成功文件；`export_artifact` 可只重试指定报价格式。客户 ZIP 仅含指定版本报价 XLSX/PDF 和公开版本/哈希清单，不打包内部成本、规格、引用或快照附件。
- 生成、同步、内部批准、客户接受分别存储；本地生成不授予后三项。PDF 中的 SIMULATED 标记保留。中文 PDF 需要支持的 TrueType 字体（`NAVOWORK_PDF_FONT`，Windows 默认尝试宋体），没有字体则该分支明确失败。

本地 manifest、结果和事件只是验证适配器。业务版本、权限及批准接入后由现有后端决定。`ArtifactTransaction` 将基线、版本登记、结果与幂等记录放在同一事务内。文件先写内容寻址 blob，提交失败可能留下不可见孤立 blob。进程强杀可能留下 `.manifest.lock`，仅确认写进程已退出后由宿主清理；本地 adapter 不提供自动抢锁或长期业务存储。

## 验收边界

`tests/contracts/` 对本地适配器与宿主 DTO/服务替身运行共享契约；替身不是 FastAPI/SQLite 真正接入测试。工具测试检查实际文件内容、哈希、公式缓存、幂等、隔离、MOQ、缺价、部分失败和人工冲突。离线模型替身检查真实 LangGraph 的多轮工具协议、重启恢复和执行限额。`tests/live/` 必须有真实模型配置才能验收模型语义与决策。

报告见 `docs/verification.md`。PDF 已做文本和页面图像检查；DOCX/XLSX 已重新打开验证，未将重开成功称为视觉检查。M5 工作台接入与扩展能力另行验收。

真实宿主适配器已实现，安装和字段映射见 [host-mapping.md](docs/host-mapping.md)。在同一环境安装 `-e './agent-kit[test]' -e './backend[test]'`，执行 `python -m pytest backend/tests agent-kit/tests -q`，可验证真实 FastAPI/SQLite/Blob 服务。本开发环境对应命令：

```powershell
$env:PYTHONPATH = 'agent-kit/.host-deps;agent-kit/.deps;agent-kit/src;backend;agent-kit/tests'
& $py -m pytest backend/tests agent-kit/tests -q
```

`.host-deps` 使用宿主精确版本的 FastAPI、SQLAlchemy、pypdf 和 reportlab 等；模型替身仍明确标记离线。工作台已增加实际文件下载入口，M5 浏览器主线尚待验收。
