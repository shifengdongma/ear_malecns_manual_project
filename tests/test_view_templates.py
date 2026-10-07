import json
import re
from ear_malecns.view_templates import research_html, workbench_html


def test_report_payload_cannot_close_script_and_roundtrips():
    data = {'text': '</script><script>alert(1)</script>', 'name': '感觉事件'}
    html = research_html(data, b'figure-bytes')
    payload = re.search(r'const D=(.*?);\n', html).group(1)
    assert '</script>' not in payload
    assert json.loads(payload) == data
    assert 'data:image/png;base64,ZmlndXJlLWJ5dGVz' in html


def test_offline_workbench_contains_sync_code_without_external_assets():
    html = workbench_html()
    assert '/*SYNC_SCRIPT*/' not in html
    assert 'function updateSynchronized' in html
    assert '<script src=' not in html
    assert '<!--OFFLINE_DATA-->' in html
