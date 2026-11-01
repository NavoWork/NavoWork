"""Read ONLY pinned Git objects; import their real Python modules in memory.

No checkout/merge, no copied source files, no uncommitted mainline reads. Test
support only; never used by the product adapter to load code or access sources.
"""

import importlib.abc
import importlib.util
from pathlib import Path
import subprocess
import sys

REVISION = "d23ab0a9ecba4dffd4ce0aa97bd496bf668aa156"
ROOT = Path(__file__).resolve().parents[3]
PREFIX = "agent-kit/src/"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


class CommittedAgentKit(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.paths = set(git("ls-tree", "-r", "--name-only", REVISION, PREFIX).decode().splitlines())

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "navowork_agent" and not fullname.startswith("navowork_agent."):
            return None
        base = PREFIX + fullname.replace(".", "/")
        is_package = base + "/__init__.py" in self.paths
        source = base + "/__init__.py" if is_package else base + ".py"
        if source not in self.paths:
            if not any(p.startswith(base + "/") for p in self.paths):
                return None
            is_package, source = True, None
        spec = importlib.util.spec_from_loader(fullname, self, is_package=is_package)
        spec.loader_state = source
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        source = module.__spec__.loader_state
        if source is None:
            return
        content = git("show", REVISION + ":" + source)
        module.__file__ = f"git-object/{REVISION}/{source}"
        exec(compile(content, module.__file__, "exec"), module.__dict__)


def install():
    if any(name == "navowork_agent" or name.startswith("navowork_agent.") for name in sys.modules):
        raise RuntimeError("Pinned compatibility tests require a process without preloaded navowork_agent")
    finder = CommittedAgentKit()
    sys.meta_path.insert(0, finder)
    return finder


def uninstall(finder):
    sys.meta_path.remove(finder)
    for name in list(sys.modules):
        if name == "navowork_agent" or name.startswith("navowork_agent.") or name == "order_skills.agentkit":
            sys.modules.pop(name)
