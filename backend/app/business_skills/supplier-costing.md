# 供应商与核价
先读取本询盘供应商原件。若用户要求使用资产库报价，search_assets → read_asset核对项目 → attach_asset(source_role=supplier_quote) → register_supplier_offer。不得自动使用未来新版包装报价。
区分含包装和不含包装、币种、每件与一次性费用。缺费用不补零；报价对比保留口径差异。MOQ不满足时停止核价并指出差额。
calculate_quote按单件成本(base+packaging+local)/汇率/(1-毛利率)上取到美分，再乘数量。公司设置可作明确缺省，用户给值优先。成本加成不是毛利率。
只保存用户请求的comparison或cost节点；客户报价需用户要求后再保存quotation。生产周期不代表到港时效，FOB不含海运及目的港税费。
