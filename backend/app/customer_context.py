from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError

from .core import fail


class BackgroundCheck(BaseModel):
    label: str = Field(max_length=100)
    status: str = Field(default="pending", pattern="^(pending|matched|review)$")
    detail: str = Field(default="", max_length=1000)


class CustomerContext(BaseModel):
    channel: str = Field(default="unknown", pattern="^(unknown|email|website|alibaba|amazon|linkedin|referral)$")
    sourceRef: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=254)
    website: str = Field(default="", max_length=500)
    linkedin: str = Field(default="", max_length=500)
    company: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    business: str = Field(default="", max_length=1000)
    summary: str = Field(default="", max_length=2000)
    simulation: bool = False
    checks: list[BackgroundCheck] = Field(default_factory=list, max_length=15)


def validate_customer_context(value):
    try:
        result = CustomerContext.model_validate(value).model_dump()
        for key in ("website", "linkedin"):
            if result[key] and (urlsplit(result[key]).scheme not in ("http", "https") or not urlsplit(result[key]).hostname):
                raise ValueError("invalid URL")
        return result
    except (ValidationError, ValueError):
        fail("INVALID_INPUT", "客户来源或背景资料格式无效；网站链接应使用 http/https")
