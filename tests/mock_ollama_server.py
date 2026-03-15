#!/usr/bin/env python3
"""Simple mock Ollama HTTP server for CI.

Reads `outputs/prompt_each_model.jsonl` and returns the parsed `raw` JSON
for the requested model at `/api/chat` or `/v1/api/chat`.
"""
import json
from pathlib import Path
from flask import Flask, request, jsonify

APP = Flask(__name__)


def load_mappings():
    p = Path('outputs') / 'prompt_each_model.jsonl'
    out = {}
    if not p.exists():
        return out
    with p.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                model = obj.get('model')
                raw = obj.get('raw')
                if model and raw:
                    try:
                        parsed = json.loads(raw)
                    except Exception:
                        parsed = {'raw': raw}
                    out[model] = parsed
            except Exception:
                continue
    return out


MAPPINGS = load_mappings()


@APP.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@APP.route('/api/chat', methods=['POST'])
@APP.route('/v1/api/chat', methods=['POST'])
def chat():
    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = {}
    model = payload.get('model') or payload.get('modelName') or ''
    resp = MAPPINGS.get(model)
    if resp is None:
        # fallback: return a simple `message` shape
        return jsonify({'message': {'content': 'Mock response: model not found'}, 'model': model})
    return jsonify(resp)


if __name__ == '__main__':
    APP.run(host='127.0.0.1', port=11435)
