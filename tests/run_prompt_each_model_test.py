import os
import json
import sys
import time
from pathlib import Path

import requests
import yaml

SERVER_URL = os.environ.get('CONTINUE_SERVER_URL', 'http://127.0.0.1:8001/chat')
JSONL_PATH = Path('outputs') / 'prompt_each_model.jsonl'
PROMPT = os.environ.get('TEST_PROMPT', 'hello world')
TIMEOUT = float(os.environ.get('TEST_TIMEOUT', '30'))


def load_saved():
    if not JSONL_PATH.exists():
        print('Missing saved results:', JSONL_PATH)
        return []
    items = []
    with JSONL_PATH.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception as e:
                print('Failed to parse line in', JSONL_PATH, e)
    return items


def call_server(prompt, model=None):
    body = {'prompt': prompt}
    if model:
        body['model'] = model
    try:
        r = requests.post(SERVER_URL, json=body, timeout=TIMEOUT)
        return r
    except Exception as e:
        return e


def main():
    # Prefer using config.yaml to determine expected models; fall back to saved outputs
    models = []
    cfg_path = Path('config.yaml')
    if cfg_path.exists():
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8'))
            for m in cfg.get('models', []):
                mm = m.get('model')
                if mm:
                    models.append(mm)
        except Exception as e:
            print('Failed to read config.yaml:', e)

    if not models:
        saved = load_saved()
        if not saved:
            print('No saved model list to test against. Run tools/prompt_each_model.py first.')
            return 2
        models = [s.get('model') for s in saved if s.get('model')]

    failures = []
    for model in models:
        print('Testing model:', model)
        resp = call_server(PROMPT, model=model)
        if isinstance(resp, Exception):
            print('  ERROR: request failed:', resp)
            failures.append((model, 'request_failed', str(resp)))
            continue
        if resp.status_code != 200:
            print('  FAIL: status', resp.status_code, resp.text[:200])
            failures.append((model, 'bad_status', resp.status_code))
            continue
        # try parse json
        try:
            data = resp.json()
        except Exception as e:
            print('  FAIL: response not JSON:', e)
            failures.append((model, 'not_json', resp.text[:500]))
            continue
        # basic check: no top-level 'error'
        if isinstance(data, dict) and data.get('error'):
            print('  FAIL: server returned error:', data.get('error'))
            failures.append((model, 'server_error', data.get('error')))
            continue
        print('  OK')
        # small delay to avoid spamming
        time.sleep(0.25)

    if failures:
        print('\nSummary: FAILURES:')
        for f in failures:
            print(' -', f)
        return 1
    print('\nAll models responded OK')
    return 0


if __name__ == '__main__':
    code = main()
    sys.exit(code)
