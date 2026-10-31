"""Customer context captured from the original inquiry; unverified links stay empty."""

def customer_context(key):
    if key.startswith("de_"):
        company, email, country = "Nordlicht Outdoor GmbH", "procurement@nordlicht.example", "德国"
        channel, source = "email", "Michael Weber · 定制背包采购邮件"
        business = "户外用品零售与定制采购；本次询价为 3,000 件背包。"
    elif key == "mx":
        company, email, country = "Luna Comercio S.A. de C.V.", "compras@luna.example", "墨西哥"
        channel, source = "email", "Sofia Hernandez · 帆布袋试单询盘"
        business = "生活方式礼品采购；拟采购 300 件帆布袋进行试单。"
    else:
        company, email, country = "Harbor Promotions Ltd.", "hello@harbor.example", "英国"
        channel, source = "email", "Emma Brown · 品牌推广项目咨询"
        business = "企业活动礼品与品牌推广；产品类型、采购量和预算待沟通。"
    return {"channel": channel, "sourceRef": source, "company": company, "country": country,
            "email": email, "website": "", "linkedin": "", "business": business,
            "summary": "客户资料来自本次询盘，采购权限与付款条件待确认。", "simulation": True,
            "checks": [{"label": "联系人与企业", "status": "pending", "detail": "已记录询盘署名与邮箱，签约主体待核验。"},
                       {"label": "官网与企业背景", "status": "pending", "detail": "待补充官网或企业登记资料。"},
                       {"label": "采购权限和付款", "status": "pending", "detail": "报价前明确采购联系人、付款主体与付款条件。"}]}
