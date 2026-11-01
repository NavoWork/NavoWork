"""Two separate Python processes resume one real SQLite graph checkpoint, offline."""
import os
from pathlib import Path
import subprocess
import sys
import json


SCRIPT = r'''
import json,sys
from pathlib import Path
from support import make_adapter,base_snapshot,change_snapshot,baselines
from test_runtime import ScriptedModel,call
from langchain_core.messages import AIMessage
from navowork_agent.runtime.agent import agent_session
from navowork_agent.tools.service import ToolService
from navowork_agent.adapters.local import LocalAdapter
from navowork_agent.contracts import ExecutionContext
root=Path(sys.argv[1])
stage=sys.argv[2]
if stage == 'start':
    a=make_adapter(root)
    snapshot=change_snapshot(a,base_snapshot(a))
    (root/'offline-snapshot.json').write_text(snapshot.model_dump_json(),encoding='utf-8')
    model=ScriptedModel([call('publish_documents',{'snapshot':snapshot.model_dump(mode='json'),'baselines':baselines(a),'intent':'initial'})])
    args={'goal':'Prepare nonprice drafts, wait for package price'}
else:
    from navowork_agent.tools.pricing import ContentSnapshot
    a=LocalAdapter(root,ExecutionContext(case_id='BAG-2026-DE-001',job_id='j_quote',run_id='run_second_process'))
    snapshot=ContentSnapshot.model_validate_json((root/'offline-snapshot.json').read_text(encoding='utf-8'))
    snapshot=change_snapshot(a,snapshot,priced=True)
    model=ScriptedModel([call('publish_documents',{'snapshot':snapshot.model_dump(mode='json'),'baselines':baselines(a),'intent':'confirmed_change'}),AIMessage(content='Finished')])
    args={'resume':{'text':'Price email supplied'}}
with agent_session(ToolService(a),model) as run:
    result=run(**args)
print(json.dumps({'status':result['status'],'outputs':len(result['outputs']),'live_executed':result['live_executed']}))
'''


def test_restart_separate_processes(tmp_path):
    kit = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(kit / "src"), str(kit / ".deps"), str(kit / "tests"), env.get("PYTHONPATH", "")])
    def run(stage):
        output = subprocess.run([sys.executable, "-c", SCRIPT, str(tmp_path / "workspace"), stage],
                                env=env, capture_output=True, text=True, timeout=45)
        assert output.returncode == 0, output.stderr
        return json.loads(output.stdout.strip().splitlines()[-1])
    first = run("start")
    assert first == {"status": "needs_info", "outputs": 4, "live_executed": False}
    second = run("resume")
    assert second == {"status": "needs_review", "outputs": 8, "live_executed": False}
