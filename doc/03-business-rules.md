# 03｜外贸领域规则与确定性计算引擎

> Owner：后端领域工程师 + 业务负责人 ｜ 状态：MVP 规则草案  
> 原则：**LLM 可以理解条件、不能作为商业数字的唯一计算者或真实交期的裁判。**

## 1. 最小业务字典（箱包 OEM/ODM）

| 概念 | 对应字段 | 易错点 |
|---|---|---|
| 款号 / SKU | `spec.model_code`, `po.line.sku` | 同一款的不同颜色/尺寸需要区分行项目 |
| 数量 | `quantity.value`, `quantity.unit` | 件/箱/套混用；颜色分项汇总不等于总数 |
| 包装 | `spec.packaging.type`, `pack.carton_qty` | 单件零售包装 ≠ 运输外箱 |
| LOGO | `spec.logo.width_mm`, `placement`, `technique` | 改尺寸可能牵动工艺、单价、样品与批准版本 |
| MOQ | `supplier_quote.moq` | MOQ 可能按颜色、款号、印刷批次计，不能只看一个总数 |
| 单价 | `cost.*`, `quotation.unit_price` | 采购价、报价和成本口径不同 |
| 贸易术语 | `trade.incoterm.rule`, `place`, `edition` | FOB 指定装运港，不意味着到港日期承诺 |
| 交期 | `plan.production_complete`, `plan.ship_date`, `customer.arrival_target` | 计划、承诺、实际三个时间维度分开 |
| 审批 | `approval.scope`, `target_version_id` | 客户批准规格 ≠ 工厂核价 ≠ 内部批准报价 |

## 2. 定价公式与货币计算

演示假设：每件原单件工厂价 ¥44 + 普通包装 ¥2 + 本地费用分摊 ¥4 = 成本 ¥50；汇率 7.20 CNY/USD；目标毛利率 20%。

```text
cost_cny_per_piece = material_and_manufacturing + packaging + allocated_local_charges
quote_usd_per_piece = ceil_cent((cost_cny_per_piece / fx_cny_per_usd) / (1 - target_gross_margin))
quote_total_usd = quote_usd_per_piece * ordered_pieces
```

**必须区分**：目标毛利 `margin=(revenue-cost)/revenue` 与成本加成 `markup=(revenue-cost)/cost`。本案例采用**毛利率**，不是 `cost * 1.2`。

```python
from decimal import Decimal, ROUND_UP

def quote_unit_price(cost_cny: str, fx_cny_per_usd: str, margin: str) -> Decimal:
    cost = Decimal(cost_cny)
    fx = Decimal(fx_cny_per_usd)
    m = Decimal(margin)
    if cost < 0 or fx <= 0 or not (Decimal("0") <= m < Decimal("1")):
        raise ValueError("Invalid price inputs")
    return (cost / fx / (Decimal("1") - m)).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )
```

**Golden Assertions**：
- A 原成本 `50` → `$8.69`；B `52` → `$9.03`。
- A 彩盒成本增加 `¥3`，新成本 `53` → `$9.21`；报价变化 `$0.52`。
- 单价应在舍入后再乘数量，还是总值舍入一次？**先作为企业定价策略配置，本演示约定“单价上取分后乘件数”**。
- 出现缺失的汇率、价格、费用范围、MOQ 或成本关键项，输出 `INCOMPLETE` 估算方案，禁止标为正式最终报价。

## 3. 不可比较的供应商报价

规范化时至少保存：

```json
{
  "supplier": "Factory-A",
  "currency": "CNY",
  "unit": "piece",
  "unit_price": "44.00",
  "includes_packaging": false,
  "included_cost_items": ["manufacturing"],
  "moq": 1000,
  "lead_time_days": 28,
  "price_valid_until": "2026-11-30",
  "source_span_id": "span_supplierA_F12"
}
```

**比较门禁**：币种不同可在已确认汇率下换算；价格口径不同（含/不含包装、税、模具、物流）必须明确列为差异项；不能将未知缺失费用默认置零。报价过期、数量不满足 MOQ 应标 `REVIEW/BLOCK`（由产品规则决定）。

## 4. PO / PI 验证规则

最小硬校验：
- `sum(line.quantity) == po.total_quantity`（注意按单位归一）；
- `sum(line.quantity * line.unit_price) == total_amount`（按约定币种/舍入策略）；
- 客户、币种、贸易术语规则及指定地点、交付口岸与已批准条款匹配；
- 产品款号/颜色分项/LOGO/包装的版本与当前允许用于签 PI 的版本一致；
- 客户 PO 的价格、付款条款、交期与已批准报价冲突时必须显示字段 Diff，不能“自动择新”。

可容许的文书表达差异与真正商务冲突分开：例如 `FOB Ningbo` 与 `FOB NINGBO` 可归一；`FOB Ningbo` 与 `FOB Shanghai` 是实质差异。

## 5. 时间、生产和运输术语规则

- `planned_date`：内部排期；`committed_date`：责任主体对外确认；`actual_date`：具证据的实际完成。
- `production_lead_days` 不等于 `arrival_lead_days`。客户要求“45 天到汉堡”必须拆分工厂生产、包装、出运、运输和潜在延误，不能等同于工厂 28 天完工。
- `FOB Ningbo, Incoterms® 2020` 以指定装运港/版本明确写入；在某些集装箱情境 FCA 可能更合适，但 P0 不自动改写客户条款，应给商务复核提示。
- 生产 T&A 只能基于已声明的日历/工作日、产能、假期等参数作候选计划；缺乏真实船期不能声称到港承诺已满足。

## 6. 从字段变化到规则触发

| 变化 | 必须触发的工具 | 后续不得越权 |
|---|---|---|
| 包装改彩盒 | `compare_versions` → `impact_analysis` → `calculate_quote` | 不自动确认新彩盒工厂交期 |
| LOGO 5cm→6cm | Spec V4 + 工艺询问 + 旧样品批准失效审查 | 不自动认为客户已批准 V4 量产 |
| 数量变 3000→3200 | MOQ、单价梯度、PO/PI、装箱方案校验 | 不自动认定供应商接受改量 |
| FOB Ningbo→FOB Shanghai | 本地费用/报价口径与合同条件复核 | 不以简单文字替换完成定价 |
| 供应商“包装报价已过期” | 成本输入过期、报价发布 Gate | 不用过期价直接报价 |

## 7. Gate 定义与失败策略

- **`QUOTE_RELEASE`**：关键报价明细完整、币种/定价策略明确、所依据事实版本已审、授权角色批准当前 Quotation Version。
- **`SPEC_ADOPTION`**：客户有效的规格/样品批准证据、版本对应且没有条件性未关闭项。
- **`PRODUCTION_RELEASE`**：已批准 PO / PI / Spec、工厂关键生产确认、包装/LOGO/样品需确认项无 BLOCK。
- **`EXTERNAL_SEND`**：可发送版本+审核过的收件人/附件/正文+真实发送权限。

Gate 返回 `{decision: allow|deny, blocking_reasons[], warnings[], evaluated_version_ids[], policy_version}`；每次批准需把版本哈希绑定进审批记录。

## 8. MVP 验收用例

1. 输入成本负数/汇率为 0/毛利率 >=1 → 明确参数错误。
2. 供应商 A/B 按 Golden 数字计算，逐次结果完全一致。
3. 彩盒缺新报价 → 仍生成候选 Spec 和询价草稿，但 Quotation **不得 RELEASE**。
4. 客户 PO 数量与已批准报价不同 → PI `needs_review`，展示差异。
5. 变更 LOGO 宽度但客户回复“looks good, but...” → `SPEC_ADOPTION` 拒绝。
6. 修改 FOB 港口但未重新核运杂费 → Quotation 重新校验，不自动套旧价格。
7. 任何用户都不能仅用聊天指令跳过 Gate。

## 9. 外部资料核对（规则来源，不应视为自动合规结论）

- ICC Incoterms 2020：https://library.iccwbo.org/content/tfb/BOOKS/BK_0049/BK_0049_05_RulesSea.htm
- 订单/单据的行业规则根据客户合同和业务审批确定，本文件只是 MVP **内部设计规则**，不是法律建议。
