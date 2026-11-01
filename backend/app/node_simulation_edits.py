"""Save canvas document edits in the local worker, without any model execution."""
import re

from .core import decode
from .domain import normalize_spec
from .workbench import append_artifact, latest_artifacts

NODE_ARTIFACT = {
    "inquiry": "inquiry_assessment", "requirements": "spec", "competitor": "competitor_analysis",
    "costing": "quotation", "risks": "risk_review", "reply": "customer_reply", "sample": "sample",
    "order": "order", "production": "production",
}


def save_edited_node(db, case, run, job, node, label):
    text = decode(job.payload)["editedText"]
    kind = NODE_ARTIFACT[node]
    previous = latest_artifacts(db, case).get(kind, {})
    content = dict(previous.get("content", {}))
    if node == "requirements":
        fields = dict(content.get("fields", {}))
        sections = re.findall(r"^(产品|数量|规格|目的地|到货要求|定制)[：:][ \t]*(.*?)(?=^(?:产品|数量|规格|目的地|到货要求|定制)[：:]|\Z)", text, re.M | re.S)
        for key, value in sections:
            value = value.strip()
            value = None if value in ("", "待确认", "待补充") else value
            if key == "规格":
                old = " / ".join(v for v in (fields.get("fabric"), fields.get("dimensions")) if v) or None
                if value != old:
                    fields.update(fabric=value, dimensions=None)
            else:
                target = {"产品": "product", "数量": "quantity", "目的地": "destination", "到货要求": "delivery", "定制": "logo"}[key]
                if key == "数量" and value:
                    value = re.sub(r"\s*件\s*$", "", value).replace(",", "")
                fields[target] = value
        content.update(normalize_spec({"fields": fields, "sourceRefs": content.get("sourceRefs", [])}))
    elif node == "risks":
        content["risks"] = [part.strip() for part in text.split("\n\n") if part.strip()]
    elif node == "reply":
        content["replies"] = {**content.get("replies", {}), "en-US": text}
    content.update(documentText=text, simulation=True, generationMode="local_mock", status="draft", manuallyEdited=True)
    append_artifact(db, case, kind, content, title=label, run_id=run.id, job_id=job.id)
    return f"已保存「{label}」的修改并生成新版本。本地 mock 处理，未调用模型 API。"
