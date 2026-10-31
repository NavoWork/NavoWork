"""Fictional acquisition and background records; no live verification claims."""
def customer_context(key):
    if key.startswith("de_"):
        company, domain, email, country = "Nordlicht Outdoor GmbH", "nordlicht.example", "procurement@nordlicht.example", "德国"
        business = "户外用品零售与企业定制采购；模拟团队规模25–50人，背包、旅行配件为主。"
        channel = {"de_a": "email", "de_b": "website", "de_c": "alibaba"}[key]
        source = {"de_a": "采购经理 Michael Weber 的直接询价邮件 · DEMO-MAIL-DE-001", "de_b": "独立站联系表单的包装续办需求 · DEMO-WEB-DE-002", "de_c": "阿里巴巴国际站老客订单跟进 · DEMO-ALI-DE-003"}[key]
        slug = "navowork-demo-nordlicht"
    elif key == "mx":
        company, domain, email, country = "Luna Comercio S.A. de C.V.", "luna.example", "compras@luna.example", "墨西哥"
        channel, source, slug = "amazon", "Amazon店铺 Luna Demo Store 的采购转介 · DEMO-AMZ-MX-001", "navowork-demo-luna"
        business = "生活方式礼品与帆布袋销售；模拟Amazon商家，希望先做小批量试单。"
    else:
        company, domain, email, country = "Harbor Promotions Ltd.", "harbor.example", "hello@harbor.example", "英国"
        channel, source, slug = "linkedin", "LinkedIn联系人 Emma Brown 的项目咨询 · DEMO-LI-UK-001", "navowork-demo-harbor"
        business = "企业活动礼品与品牌推广；本次项目的具体包型、预算和采购量尚待澄清。"
    return {"channel": channel, "sourceRef": source, "company": company, "country": country,
            "email": email, "website": f"https://{domain}", "linkedin": f"https://www.linkedin.com/company/{slug}/",
            "business": business, "summary": "模拟资料中的公司名称、采购联系人和邮件域名一致；采购决策权限、公司注册与付款信誉仍需核验。", "simulation": True,
            "checks": [{"label": "公司与邮件一致性", "status": "matched", "detail": "演示原件的公司和联系人字段一致；并非真实工商验证。"},
                       {"label": "官网与社交资料", "status": "review", "detail": "提供虚构官网与LinkedIn示例，供演示核对主营业务和联系人。"},
                       {"label": "采购权限和付款信誉", "status": "pending", "detail": "正式交易前应核验联系人权限、签约主体和付款条件；没有预设信用评级。"}]}
