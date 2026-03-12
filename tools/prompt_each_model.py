import os
import subprocess
import requests
import json

OLLAMA_BASE = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11435')
CHAT_PATHS = ['/api/chat', '/v1/api/chat']

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
            return True, resp.text
        except Exception as e:
            last_exc = e
            continue
    return False, str(last_exc)


def main():
    models = list_models()
    if not models:
        print('No models found.')
        return
    out = []
    for m in models:
        print(f'Prompting model: {m}')
        ok, text = prompt_model(m)
        print('OK' if ok else 'FAIL', '-', text[:1000])
        out.append({'model': m, 'ok': ok, 'raw': text})
    # write results
    os.makedirs('outputs', exist_ok=True)
    with open('outputs/prompt_each_model.jsonl', 'w', encoding='utf-8') as f:
        for item in out:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print('Wrote outputs/prompt_each_model.jsonl')

if __name__ == '__main__':
    main()
