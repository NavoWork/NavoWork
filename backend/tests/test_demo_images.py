from io import BytesIO

import pytest
from docx import Document

from app import concept_images, demo_images
from app.demo_scenarios import scenario_inputs
from test_workbench_v2 import _start, _finish

BASE = '/api/v1/workspaces/ws_demo/inquiries'


def no_image_api(*args, **kwargs):
    raise AssertionError('Demo playback must never call an image provider')


@pytest.mark.parametrize('scenario_id', sorted(demo_images.PRESETS))
def test_every_demo_uses_its_local_image_and_saves_chat_exports(client, other_client, monkeypatch, scenario_id):
    monkeypatch.setattr(concept_images, 'generate_image', no_image_api)
    monkeypatch.setattr(concept_images, 'image_settings', no_image_api)
    # Even available provider credentials must not change demo playback.
    monkeypatch.setenv('IMAGE_API_KEY', 'unused-image-key')
    case = client.post(BASE, json={'demoScenarioId': scenario_id}).json()
    path = BASE + '/' + case['id']
    capability = client.get(path + '/workbench/capabilities').json()['image']
    assert capability['configured'] and capability['mode'] == 'preset'
    assert 'unused-image-key' not in str(capability)
    assert client.get(path + '/workbench').json()['artifacts'] == {}
    toolbox, run, job, work, _ = _start(client, path, None, '请准备产品概念图')
    fields = scenario_inputs(scenario_id)['fields']
    assert toolbox.call('update_requirements', {'fields': fields})['status'] == 'success'
    context = toolbox.call('get_case_context', {})['data']
    assert context['imageCapability']['mode'] == 'preset'
    result = toolbox.call('generate_concept_image', {
        'spec_version_id': context['artifacts']['spec']['id'], 'prompt': 'Product concept for the current inquiry', 'base_version': 0,
    })
    assert result['status'] == 'needs_review', result
    content = result['artifact']['content']
    assert content['generationMode'] == 'preset' and content['presetId'] == scenario_id
    assert content['simulation'] is True and content['imageApiCalled'] is False
    _finish(run, job, work, None)
    messages = client.get(path + '/messages').json()['items']
    image = next(m['images'][0] for m in messages if m.get('runId') == run and m['role'] == 'assistant')
    assert image['generationMode'] == 'preset'
    assert client.get(image['url']).content == demo_images.preset_path(scenario_id).read_bytes()
    assert other_client.get(image['url']).status_code == 404
    assert other_client.get(image['proposalUrl']).status_code == 404
    proposal = Document(BytesIO(client.get(image['proposalUrl']).content))
    assert len(proposal.inline_shapes) == 1
    assert 'no image API was called' in ' '.join(p.text for p in proposal.paragraphs)
    # Another version keeps the original image immutable and uses the same preset.
    before = client.get(path).json()['currentRevision']
    second = client.post(path + '/workbench/research/concepts', json={
        'baseRevision': before, 'spec_version_id': content['specVersionId'], 'prompt': 'A second design brief', 'base_version': 1,
    }).json()
    assert second['status'] == 'needs_review', second
    assert second['artifact']['version'] == 2
    assert client.get(image['url']).content == client.get(second['export']['downloadUrl']).content


def test_missing_preset_blocks_without_falling_back_to_an_api(client, monkeypatch, tmp_path):
    monkeypatch.setattr(concept_images, 'generate_image', no_image_api)
    monkeypatch.setattr(concept_images, 'image_settings', no_image_api)
    monkeypatch.setattr(demo_images, 'ASSET_DIR', tmp_path)
    case = client.post(BASE, json={'demoScenarioId': 'de-backpack'}).json()
    path = BASE + '/' + case['id']
    assert client.get(path + '/workbench/capabilities').json()['image']['configured'] is False
    toolbox, *_ = _start(client, path, None, '请准备产品概念图')
    toolbox.call('update_requirements', {'fields': scenario_inputs('de-backpack')['fields']})
    spec = toolbox.call('get_case_context', {})['data']['artifacts']['spec']['id']
    result = toolbox.call('generate_concept_image', {'spec_version_id': spec, 'prompt': 'Backpack', 'base_version': 0})
    assert result['code'] == 'DEMO_IMAGE_UNAVAILABLE'
    assert 'concept_image' not in client.get(path + '/workbench').json()['artifacts']
