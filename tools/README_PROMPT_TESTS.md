## Running Prompt Tests Locally

You can test the `prompt_each_model.py` script without a live Ollama server using the mock mode:

1. Prepare the mock models file (included as `tools/mock_models.txt`):

```
mistral:7b
qwen3:1.7b
qwen2-math:1.5b
```

2. Run the script with a prompt and the mock toggle:

```bash
python tools/prompt_each_model.py --prompt "hello world" --models-file tools/mock_models.txt --mock
```

3. Output is written as structured JSONL to `outputs/prompt_each_model.jsonl`, e.g.:

```json
{"model": "mistral:7b", "prompt": "hello world", "ok": true, "status_code": 200, "request_id": "abc123", "response": {"text": "Hello from Mistral mock!"}}
```

This allows testing parsing, CI integration, or local development without connecting to a real Ollama server.
