"""Temporary dependency-injection seam, to be replaced with agent-kit imports.

Objects named context/file_ref/citation/result belong to the host. This module
does not define substitutes for shared protocols or register a tool/Worker.
"""
from __future__ import annotations

import copy
from typing import Any, Protocol

from .adapters import AdapterError, VisionAdapter
from .core import InputError, recognize


class HostPorts(Protocol):
    def authorize_file(self, context: Any, file_ref: dict) -> None:
        """Raise unless this Case may read this exact immutable file version."""
        ...

    def read_file(self, context: Any, file_ref: dict) -> bytes: ...

    def make_citation(self, context: Any, file_ref: dict, sha256: str, locator: dict) -> Any: ...

    def make_result(self, context: Any, *, data: dict, citations: list[Any]) -> Any: ...


def recognize_tool(context: Any, file_ref: dict, *, ports: HostPorts | None,
                   adapter: VisionAdapter | None) -> Any:
    """Local blocked envelopes are diagnostic only; host success uses real factories."""
    if context is None or not isinstance(file_ref, dict) or not file_ref:
        return {"status": "blocked", "dependency": "ExecutionContext/FileRef"}
    if ports is None or not all(callable(getattr(ports, name, None)) for name in (
        "authorize_file", "read_file", "make_citation", "make_result"
    )):
        return {"status": "blocked", "dependency": "authorized file tools / Citation / ToolResult factories"}
    if adapter is None:
        return {"status": "blocked", "dependency": "vision adapter"}
    try:
        # Each host call gets an equivalent detached reference: no accidental mutation
        # by a port can redirect a subsequent read to another file/version.
        ref = copy.deepcopy(file_ref)
        ports.authorize_file(context, copy.deepcopy(ref))
        image = ports.read_file(context, copy.deepcopy(ref))
        data = recognize(image, ref, adapter)
        locators = [{"kind": "image", "raw_text": data["raw_text"]}]
        locators.extend(row["source"] for row in data["rows"])
        citations = [ports.make_citation(context, copy.deepcopy(ref), data["source"]["sha256"],
                                         copy.deepcopy(locator)) for locator in locators]
        return ports.make_result(context, data=data, citations=citations)
    except (InputError, AdapterError) as exc:
        return {"status": "blocked", "dependency": "recognition", "code": str(exc)}
    except Exception:
        # Host exceptions can contain storage paths, credentials or document bodies.
        return {"status": "blocked", "dependency": "host authorization/file/result ports"}
