"""Render current UI over frozen results without modifying scientific artifacts."""
import base64
import json
from pathlib import Path

PACKAGE = Path(__file__).parent


def workbench_html():
    template = (PACKAGE / 'workbench_template.html').read_text(encoding='utf-8')
    script = (PACKAGE / 'workbench_sync.js').read_text(encoding='utf-8')
    return template.replace('/*SYNC_SCRIPT*/', script)


def research_html(data, figure):
    template = (PACKAGE / 'research_report_template.html').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    return template.replace('/*RESULTS*/', payload).replace('FIGURE_DATA', base64.b64encode(figure).decode())
