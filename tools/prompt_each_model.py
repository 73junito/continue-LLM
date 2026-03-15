import os
import subprocess
import requests
import json
import argparse

OLLAMA_BASE = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11435')
CHAT_PATHS = ['/api/chat', '/v1/api/chat']


def fetch_models(base_url=OLLAMA_BASE):
    url = base_url.rstrip('/') + '/models'
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get('name') for m in data.get('models', []) if isinstance(m, dict) and m.get('name')]
        return models
    except Exception as e:
        print(f'Failed to fetch models from {url}:', e)
        return []

def list_models():
    try:
        r = subprocess.run(['ollama', 'list'], capture_output=True, text=True, check=True)
    except Exception as e:
        print('Failed to run `ollama list`:', e)
        return []
    models = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith('name'):
            continue
        parts = line.split()
        if parts:
            models.append(parts[0])
    return models


def prompt_model(model, prompt='hello world'):
    body = {
        'stream': False,
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt}
        ]
    }
    last_exc = None
    for path in CHAT_PATHS:
        url = OLLAMA_BASE.rstrip('/') + path
        try:
            resp = requests.post(url, json=body, timeout=60)
            resp.raise_for_status()
            # try to parse JSON response, but fall back to text
            parsed = None
            try:
                parsed = resp.json()
            except Exception:
                parsed = resp.text

            # attempt to capture request id headers if present
            request_id = resp.headers.get('request-id') or resp.headers.get('x-request-id')

            return True, {'status_code': resp.status_code, 'request_id': request_id, 'body': parsed}
        except Exception as e:
            last_exc = e
            continue
    return False, str(last_exc)


def load_models_from_file(path):
    if not os.path.exists(path):
        return []
    models = []
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                models.append(line)
    except Exception:
        return []
    return models


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompt', '-p', help='Prompt to send', default=os.environ.get('PROMPT', 'hello world'))
    parser.add_argument('--models-file', '-m', help='Optional file with model names (one per line)')
    parser.add_argument('--mock', action='store_true', help='Use mock responses instead of calling Ollama')
    args = parser.parse_args()

    if args.models_file:
        models = load_models_from_file(args.models_file)
    else:
        # prefer /models discovery, fall back to `ollama list`
        models = fetch_models(OLLAMA_BASE)
        if not models:
            models = list_models()

    if not models:
        print('No models found.')
        return

    out = []
    os.makedirs('outputs', exist_ok=True)
    out_path = os.path.join('outputs', 'prompt_each_model.jsonl')

    for m in models:
        print(f'Prompting model: {m}')
        if args.mock:
            # produce a stubbed response for testing
            record = {
                'model': m,
                'prompt': args.prompt,
                'ok': True,
                'status_code': 200,
                'request_id': f'mock-{m}',
                'response': {'text': f'Mock response for {m}: {args.prompt}'}
            }
            print('MOCK OK -', record['response']['text'])
        else:
            ok, resp = prompt_model(m, prompt=args.prompt)
            if ok:
                record = {
                    'model': m,
                    'prompt': args.prompt,
                    'ok': True,
                    'status_code': resp.get('status_code') if isinstance(resp, dict) else None,
                    'request_id': resp.get('request_id') if isinstance(resp, dict) else None,
                    'response': resp.get('body') if isinstance(resp, dict) else resp,
                }
                print('OK -', json.dumps(record['response'])[:1000])
            else:
                record = {'model': m, 'prompt': args.prompt, 'ok': False, 'error': resp}
                print('FAIL -', resp)

        out.append(record)

    with open(out_path, 'w', encoding='utf-8') as f:
        for item in out:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f'Wrote {out_path}')

if __name__ == '__main__':
    main()
