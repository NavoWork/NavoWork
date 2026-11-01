# guilimao 基线合入与 PRD 验收（2026-11-01）

本轮以 `origin/guilimao@3fe1581` 为架构基线，在 `codex/guilimao-foundation` 汇总后快进 `integration/guilimao-baseline`。远端 `lirui@ddd6f6a` 的独立 Agent 能力按实际工具迁移，不将旧 `business_agent` 主循环重新覆盖 guilimao 工作台。此前 `18242d5` 只合入了文件子任务；本文对应本轮新增的研究、视觉、依赖与 Office 能力，不将旧提交当成这些能力的合入证明。

## 按 PRD 核对的结果

| PRD 范围 | 当前实现与可观察验收 | 代码与证据 |
| --- | --- | --- |
| §1–5 连续 Case / W1 / W2 | 保留原生业务工具、来源、人工批准和放行门禁；文件编辑加入同一 Agent。缺资料保存断点，补充后继续；失败不能被聊天宣称成功 | `agent_runtime.py`、`agent_tools.py`、`test_native_agent_context.py`、`test_workbench_v2.py` |
| §6 竞品分析 | 资料原文摘录、哈希、精确定位、观察日期/适用范围；比较与候选建议分开，显式采纳进入设计简报，不覆盖客户要求 | `research_tools.py`、`research_api.py`、`test_research_tools.py`、实际浏览器研究流程 |
| §7 概念图 | 配置式真实服务接口；输入绑定规格/修订/租约；保存 PNG/JPEG、失败与重试、含图和同规格的可编辑提案 DOCX；视觉匹配待人审 | `concept_images.py`、研究面板；真实 provider 验收尚未执行 |
| §8 BOM 图片/表格 | PNG/JPEG VLM 候选保留原件/定位/不确定项/合计校验，纠正生成新版本，不自动批准价格；真实 XLSX 文件读取/编辑与 Decimal 核价 | `bom_vision_service.py`、`extensions/bom-vision`、研究与 Office 测试 |
| §9 Office 编辑 | 实际 DOCX 标题/段落/基本样式/表格/图片插入替换；XLSX 单元格/样式/区域复制/行列增删/支持公式缓存；预览、保存、原生下载和历史只读 | `office_files.py`、`OfficeFiles.tsx`、`test_office_files.py`、实际 Edge 浏览器测试 |
| §9.2 编辑触发联动 | 系统规格 DOCX/XLSX 数量编辑100→200后自动重算成本/报价至2626.00；BOM XLSX 用量2→3后自动核价20.00。来源/标签/旧基线冲突保存草稿，不覆写新事实 | `office-spec-field-map-v1`、`office-bom-row-map-v1`；后端与浏览器验证 |
| §9.3–9.5 原生导出 | DOCX/XLSX/PDF 真文件，绑定不可变成果版本；客户报价/PI从公开白名单重建，内部成本/供应商/毛利不进入客户文件 | `exports.py`、`test_public_exports.py`；Office PDF明确为内容预览 |
| §10 依赖闭环 | 精确版本边与字段定位、拒绝循环；旧成果/导出立即失效；拓扑重算数量→成本→报价→订单差异/PI草稿金额与条款，显式BOM行→成本；统一快照/一致性ID；成功格式保留、失败节点/格式单独重试；CAS拒绝迟到任务 | `propagation.py`、`test_propagation.py`、跨文件同步面板 |
| §10–12 事实/批准保护 | 新草稿不继承批准；保留原PO、历史批准/导出。数量变化不无故重生图或作废实物样品批准；物理规格变化需要复核。未知映射披露覆盖不完整 | 显式字段规则、样品物理规格兼容检查、权限/失败测试 |

## 实现范围和仍待验收的缺口

1. **真实图像/VLM 端到端质量验收未完成。** 按用户安排交由配置伙伴补齐。已提供默认跳过的 opt-in 测试，不以 mock 成功代替供应商调用成功。用户提供 TokenHub 的 `TOKENHUB_API_KEY` / Responses 路由信息；当前产品图像 adapter 使用 `/images/generations`、VLM 使用 chat-completions。TokenHub Responses 专用桥接、准确模型名称、凭据映射和现场图像质量需由伙伴核验；不自动读取个人 Codex 凭据，也未消费其额度。
2. **自动业务改写仅限登记过的映射。** 规格数量、报价基础条款、显式 BOM 行绑定和订单比较可确定性执行。材料/结构/LOGO变更会使对应图、BOM适用性和样品进入待复核，不会猜测新价格/用量或冒充图像视觉检查通过。新增自由文件/复杂表格须登记映射才能进入自动改写范围；未登记内容可保存但不能宣称全部同步。
3. **图像检查仍需人工。** 目前概念图始终标记 `visualAlignment=needs_human_review`，LOGO默认中性占位；上传原图可在文档内替换。没有视觉相符性模型验收，不宣称准确制造参数、实物样品批准或工程图能力。
4. **Office 支持基础兼容范围。** 支持同表相对引用、四则运算、SUM、ROUND、ROUNDUP；外部/绝对/跨表引用、宏、未知函数不执行。带公式工作簿的结构变更会拒绝，界面保留未保存输入。PDF与页面读取相同文件字节，但内容预览不等同 Word/Excel 分页、页眉页脚和复杂模板无损渲染。
5. **工作空间隔离已有，操作系统沙箱未引入。** 受控工具无任意路径、shell或代码执行；Case ACL、版本、租约、哈希及源文件只读负责隔离。若后续允许任意代码/二进制工具执行，需要单独的进程/容器沙箱。Wiki语义关联仅可作为候选；Neo4j/LLMWiki不属于本轮必须依赖。
6. **PRD之外的真实业务事件未执行。** 无真实客户外发、合同签署、收款核验、采购或量产；生成/已同步/批准/已发送仍为独立状态。

## 本轮回归结果

- 后端：87 passed，2 skipped（真实图像/VLM opt-in）。
- Agent Kit：39 passed，1 skipped（真实模型），5 subtests passed。
- BOM vision 扩展：38 passed。
- Order skills 扩展：71 passed，2 skipped，53 subtests passed。
- 前端：类型检查、30项单测和生产构建通过。
- 实际 Edge 浏览器：2项通过，包含原件/历史保护、公式6→15、竞品采纳和规格Office编辑自动同步。

不同扩展的测试应在其安装/PYTHONPATH包含对应包根目录的环境中运行；缺包导致的测试收集失败不是产品通过证据。上述结果来自配置正确后的独立执行。

## 验证方式

常规回归默认禁止外部模型调用，数据库和文件存储使用测试临时目录。

```powershell
python -m pytest backend/tests agent-kit/tests -q -p no:cacheprovider
$env:PYTHONPATH="extensions/bom-vision;extensions/order-skills;agent-kit/src"
python -m pytest extensions/bom-vision/tests extensions/order-skills/tests -q -p no:cacheprovider
npm run typecheck
npm run test
npm run build
```

Office 浏览器测试使用独立 API/SQLite/storage（测试环境 `APP_ENV=demo`），和 real 模式 Vite，API/UI分别8017/5187；可用 `OFFICE_UI_URL` 改浏览器入口。启动 API：设置 `DATABASE_URL`、`STORAGE_ROOT`、`ALLOWED_ORIGINS=http://127.0.0.1:5187` 后 `python -m uvicorn app.main:app --app-dir backend --port 8017`；UI在 `fontend` 中设置 `VITE_API_MODE=real`、`API_PROXY_TARGET=http://127.0.0.1:8017` 后 `npx vite --host 127.0.0.1 --port 5187`。

```powershell
cd fontend
npx playwright test --config playwright.office.config.ts
```

真实服务验收另见 [执行说明](../backend/tests/live/README.md)。测试所用虚构成本和 BOM 不属于真实供应商报价。
