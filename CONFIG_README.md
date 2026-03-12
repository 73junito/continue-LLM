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

### Ollama

```yaml
provider: ollama
apiBase: http://localhost:11434
apiVersion: v1
timeout: 5000
models:
  - id: llama3
    name: llama3
    modelArgs:
      temperature: 0.7
```

### OpenAI

```yaml
provider: openai
apiKey: sk-XXXX
timeout: 10000
models:
  - id: gpt-4
    name: gpt-4
    modelArgs:
      temperature: 1
```

### Anthropic

```yaml
provider: anthropic
apiKey: sk-XXXX
timeout: 10000
models:
  - id: claude-v1
    name: claude-v1
    modelArgs:
      temperature: 0.9
```

### Local

```yaml
provider: local
apiBase: http://localhost:11434
apiVersion: v1
timeout: 5000
models:
  - id: local-model
    name: local-model
```
