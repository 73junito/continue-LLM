# Configuration README

This repository uses a simple YAML configuration file `config.yaml` describing models, routing rules, and default runtime values.

Top-level keys

- `name` (string, required): Human-friendly config name.
- `version` (string, required): Config version string.
- `schema` (string, required): Schema version identifier (e.g., `v1`).
- `models` (array, required): List of model definitions. Each item:
  - `id` (string, required): Short identifier used by routes.
  - `name` (string, required): Display name.
  - `description` (string, optional): Human description.
  - `provider` (string, required): Provider name (e.g., `ollama`).
  - `model` (string, required): Provider model reference.
  - `apiBase` (string, optional, uri): Base URL for provider API.
- `routes` (array, required): Routing rules that map input patterns to model `id`.
  - `match` (string, required): Regex or pattern to match user intent.
  - `model` (string, required): `id` of a model from `models`.
- `defaults` (object, required): Runtime defaults
  - `timeout_seconds` (integer, required): Request timeout in seconds.
  - `max_tokens` (integer, required): Max tokens for model calls.

Validation

Run the validator (requires Node packages listed in `package.json`):

```bash
npm install
npm run validate-config
```

If validation fails, the script prints `validate.errors` with Ajv details.

Example snippet

```yaml
name: Local Config
version: 1.0.0
schema: v1

models:
  - id: explanation
    name: Llama3
    provider: ollama
    model: llama3:latest
    apiBase: 'http://localhost:11434'

routes:
  - match: '(explain|summary)'
    model: explanation

defaults:
  timeout_seconds: 120
  max_tokens: 8192
```

Next steps

- Add CI step to run `npm run validate-config` on PRs.
- Extend schema enums for `provider` if you want stricter validation.

## Provider Examples

Each example below shows a valid `models` entry for the respective provider. Place these entries inside the `models` array in your `config.yaml`.

### Ollama

```yaml
models:
  - id: llama3
    name: Llama 3
    description: 'Local Llama 3 model via Ollama.'
    provider: ollama
    model: llama3:latest
    apiBase: http://localhost:11434
```

### OpenAI

```yaml
models:
  - id: gpt-4
    name: GPT-4
    description: 'OpenAI GPT-4 model.'
    provider: openai
    model: gpt-4
    apiKey: sk-XXXX
```

### Anthropic

```yaml
models:
  - id: claude-v1
    name: Claude v1
    description: 'Anthropic Claude v1 model.'
    provider: anthropic
    model: claude-instant-1
    apiKey: sk-ant-XXXX
```

### Local

```yaml
models:
  - id: local-model
    name: Local Model
    description: 'Custom local model.'
    provider: local
    model: local:latest
    apiBase: http://localhost:11434
```
