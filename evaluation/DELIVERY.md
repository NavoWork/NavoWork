# 交付与验收记录（2026-10-31）

实现范围仅 `evaluation/`，独立 worktree `C:/Users/Justike/.codex/worktrees/de72/NavoWork`，分支 `codex/agent-evaluation`。启动核验 HEAD=`4e34ce0958912fc3326358589a520cbf38c5103e`，并确认包含 `origin/lirui` 的约定提交 `5fcf0a1`。未合并回 justike，未操作共享 checkout 的分支或暂存区。测试期间 HEAD 为上述基线，新评测代码的实际文件 SHA-256 已写进报告 `implementation_files`，用于绑定随后提交的实现。

## 第一阶段：独立评测能力

已实现 `python -m evaluation`，支持 list / run / self-test / backend-probe，以及 module、stdin/stdout CLI、HTTP 适配器；协议与未来主链路映射见 [PROTOCOL.md](PROTOCOL.md)。报告为 JSON，配套纯文本失败清单。

| 验证项 | 实际结果 | 证据 |
| --- | --- | --- |
| 自动化测试 | 21 项通过；含两个数值种子、篡改、越界、超时、损坏响应与模块/CLI/HTTP 回环 | [unit-tests.json](reports/unit-tests.json)、[完整日志](reports/unit-tests.txt) |
| 正确离线对照 | 13/13 场景通过，基于实际文件内容和独立金额 oracle | [offline-control.json](reports/offline-control.json) |
| 评测器变异自测 | 13/13 故障命中指定不变量，0 存活 | [mutation-summary.json](reports/mutation-summary.json) |
| 无运行时 | 13 场景均 blocked，0 被误报通过 | [runtime-blocked.json](reports/runtime-blocked.json) |
| 文件内容 | 已读原 EML/XLSX/PDF，检查实际 JSON/HTML/ZIP 成果、来源定位、哈希和版本关系 | offline-control 的 output_evidence、input_inventory |
| 文件视觉 | 未执行渲染或视觉审阅 | 报告 file_visual=not_performed |
| 真实模型 | 未执行；无模型 API 请求 | 报告 real_model=not_executed |

可简读四类关键故障的失败记录：

- [金额错误](reports/mutation-amount-failures.txt)：即使缺陷端同步改了文件、返回值和哈希，仍由独立 oracle 检出。
- [读取旧内容](reports/mutation-stale-failures.txt)：同名不同内容的版本引用、读取事件与固定来源哈希不符。
- [伪造成功](reports/mutation-false_success-failures.txt)：部分导出失败被报 ready、无邮件连接器却生成 sent_at。
- [客户成本泄露](reports/mutation-customer_leak-failures.txt)：实际 ZIP 内夹带内部原始邮件，递归读取后检出。

完整运行证据保留在本 worktree 的 `evaluation/runs/delivery-selftest/`，不随 Git 提交；报告中的 evidence_directory 指向对应目录。另一 checkout 可按 README 重跑生成。生成输入只临时写入 evaluation/runs，未改或重建 test/。测试为离线能力和传输协议自测，不验证真实服务的认证、权限持久化、数据库事务或 Worker。

## 已观察的后端函数行为

见 [backend-observations.json](reports/backend-observations.json)，包含实际源码 SHA-256、函数行号和观察范围。只执行选取的函数 AST，协作者均为内存替身，未导入/启动后端服务：

1. `worker.build_revision` 输入需求数量 3200、核价数量 3000，输出仍保留两种数量及 3000 对应的小计，没有在此函数协调。
2. `agent.understand_node` 输入新正文 4800 件、既有字段 3000 件、无数量的“分析更新资料”指令，离线提取后仍得到 3000。
3. `agent.draft_node` 将内部来源摘录写入规格成果，`exports.export_artifact(..., html)` 保留该摘录。通用成果导出观察到内部摘录，不等于已复现客户包泄露。

真实服务的伪成功、客户受众材料包均记为 `not_tested`。四类风险的评测器检出能力由故障适配器证明，不能把它们冒充真实后端复现。

## 前置资料一致性失败

原有只读校验器 `test/scripts/validate_fixtures.py` 和 `validate_core15.py` 均退出 1，完整输出见 [existing-fixture-validators.json](reports/existing-fixture-validators.json)。43 个声明哈希检查中有 8 项不一致，详见报告 declared_fixture_integrity 和 [简明失败清单](reports/offline-failures.txt)：

- 5 份原 PDF：factory-B-quote、po-correct、po-conflict、supplier-incomplete、supplier-reply。当前 raw hash 不符；替换 CRLF 为 LF 后与声明相符。Git 显示 i/lf、w/crlf，core.autocrlf=true。
- 3 封 core15 历史副本：original-inquiry、original-change-color-box、original-customer-conditional-confirmation。当前 raw hash 不符，简单 LF 归一化也不等于声明。

没有修复原文件、调整根 Git 配置、更新 oracle 或重新 seal。场景检查针对实际读取字节通过；声明来源一致性失败是独立的产品验收前置阻断，不能因场景通过而忽略。core15 后续批准邮件从未进入早期缺证场景或任何被测 Agent 请求。

## 第二阶段：主链路接入与产品验收

**blocked / 产品未验收。** 本基线和本地 refs 的 `git log --all -- agent-kit` 无可核对的已提交协议；未读取或复制主执行 chat 的未提交内容。

待主链路提供已提交协议和运行接口后：

1. 对齐 ExecutionContext/FileRef/Citation/ToolResult，受信任 shim 注入身份、Case、固定版本与批准范围，禁止 Prompt 自授权限。
2. 用真实文件工具、工具注册、Worker 与宿主日志运行相同场景；跨 Case 场景须先在外 Case 入库真实来源，不能仅以未知 ID 的 404 证明权限。
3. 在真实导出提供者注入部分失败，验证数据库/实际文件/事件一致及幂等；故障控制不进入模型 Prompt。
4. 记录模型 provider、model、request_id 和输入输出哈希，并与独立宿主追踪对账。适配器自报模型事件只记 reported_unverified。
5. 在浏览器跑实际用户路径，对下载的 PDF/XLSX 做渲染及视觉审阅，另出报告。修复或明确接受原始素材哈希前置问题。

当前没有真实模型、主链路接入、文件视觉验收或完整产品通过结论。
