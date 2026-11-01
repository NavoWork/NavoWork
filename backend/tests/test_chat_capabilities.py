import pytest

from app.core import decode
from app.db import SessionLocal
from app.models import Case, Job, Run, WorkItem
from test_workbench_v2 import _start, _finish

BASE = '/api/v1/workspaces/ws_demo'
CASE = BASE + '/inquiries/inq_demo_bag'


def test_image_configuration_does_not_reuse_chat_credentials(client, monkeypatch):
    from app.concept_images import ConceptImageError, image_settings
    monkeypatch.setenv('MODEL_API_KEY', 'chat-only-test-key')
    monkeypatch.setenv('MODEL_BASE_URL', 'https://chat.example/v1')
    monkeypatch.setenv('IMAGE_MODEL', 'image-test-model')
    monkeypatch.delenv('IMAGE_API_KEY', raising=False)
    monkeypatch.delenv('IMAGE_MODEL_API_KEY', raising=False)
    with pytest.raises(ConceptImageError, match='未配置模型密钥'):
        image_settings()
    capabilities = client.get(CASE + '/workbench/capabilities').json()
    assert capabilities['image']['configured'] is False
    assert 'chat-only-test-key' not in str(capabilities)
    monkeypatch.setenv('IMAGE_API_KEY', 'dedicated-image-key')
    monkeypatch.setenv('IMAGE_BASE_URL', 'https://images.example/v1')
    settings = image_settings()
    assert settings['base_url'] == 'https://images.example/v1'
    assert settings['api_key'] == 'dedicated-image-key'


def test_free_chat_uses_inquiry_history_and_excludes_other_inquiries(client, monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from app.agent_runtime import execute_agent_work
    foreign = client.post(BASE + '/inquiries', json={'title': '其他询盘', 'customer': 'Other', 'originalText': 'Other chat private instruction'}).json()
    assert foreign['id'] != 'inq_demo_bag'
    from app.core import create_item
    with SessionLocal() as db:
        create_item(db, 'message', {'role': 'user', 'text': '这个方案请突出蓝色和通勤风格', 'conversationId': 'old_chat'}, case_id='inq_demo_bag')
        db.commit()
    response = client.post(CASE + '/workbench/agent', json={'instruction': '按照我刚才说的风格，写一句标题', 'baseRevision': 0})
    assert response.status_code == 200, response.text
    run_id = response.json()['id']
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        job = db.get(Job, run.job_id)
        history = decode(job.payload)['chatHistory']
        assert '这个方案请突出蓝色和通勤风格' in [m['text'] for m in history]
        assert 'Other chat private instruction' not in str(history)
        assert decode(job.payload)['agentNode'] is None
        work = db.query(WorkItem).filter_by(run_id=run_id).one()
        work.status = job.status = run.status = 'running'
        work.lease_generation = 1
        work.lease_expires_at = '2999-01-01T00:00:00Z'
        work_id = work.id
        db.commit()

    class Model:
        def bind_tools(self, schemas):
            assert 'generate_concept_image' in [s['function']['name'] for s in schemas]
            return self

        def invoke(self, messages):
            text = '\n'.join(str(m.content) for m in messages)
            assert '突出蓝色和通勤风格' in text
            assert 'Other chat private instruction' not in text
            return AIMessage(content='蓝调通勤，轻装出发。')

    monkeypatch.setenv('WORKBENCH_AGENT_CHECKPOINT_DB', str(tmp_path / 'chat.sqlite3'))
    execute_agent_work(work_id, 1, model=Model())
    result = client.get(BASE + '/runs/' + run_id).json()
    assert result['status'] == 'succeeded'
    assert client.get(CASE).json()['currentRevision'] == 0


def test_generated_image_is_saved_with_chat_message(client, other_client, monkeypatch):
    from app import concept_images
    from test_research_tools import ImageProvider, png
    generate = concept_images.generate_image
    monkeypatch.setattr(concept_images, 'generate_image', lambda prompt, **kwargs: generate(prompt, provider=ImageProvider()))
    toolbox, run_id, job_id, work_id, _ = _start(client, CASE, None, '请生成产品设计图')
    spec = toolbox.call('update_requirements', {'fields': {'product': 'canvas tote', 'fabric': 'cotton canvas'}})
    assert spec['status'] == 'success'
    context = toolbox.call('get_case_context', {})['data']
    result = toolbox.call('generate_concept_image', {'spec_version_id': context['artifacts']['spec']['id'], 'prompt': 'Blue commuter tote on a neutral background', 'base_version': 0})
    assert result['status'] == 'needs_review', result
    _finish(run_id, job_id, work_id, None)
    messages = client.get(CASE + '/messages').json()['items']
    message = next(m for m in messages if m.get('runId') == run_id and m['role'] == 'assistant')
    assert len(message['images']) == 1
    image = message['images'][0]
    assert client.get(image['url']).content == png()
    assert client.get(image['proposalUrl']).status_code == 200
    assert other_client.get(image['url']).status_code == 404
    assert image['version'] == 1
