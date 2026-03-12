from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import requests
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from requests.exceptions import RequestException
import re


# JSON structured logging formatter
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Use timezone-aware UTC timestamp to avoid deprecation warnings
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        level = record.levelname
        msg = record.getMessage()
        request_id = getattr(record, 'request_id', None)
        payload = {
            'timestamp': ts,
            'level': level,
            'request_id': request_id,
            'message': msg,
        }
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload)


# Configure root logger once (guard against double-imports in tests)
root_logger = logging.getLogger()
if not root_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def _extract_json_block(text: str):
    """Find and parse a JSON object inside arbitrary text.

    Returns the parsed JSON (dict/list) or None if not found/parsable.
    """
    if not isinstance(text, str):
        return None
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start:end+1]
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _try_parse_json_like(text: str):
    """Try several heuristics to interpret `text` as JSON.

    Returns a tuple (success: bool, value)
    """
    if not isinstance(text, str):
        return False, text
    s = text.strip()
    if not s:
        return False, text
    # Direct JSON
    try:
        return True, json.loads(s)
    except Exception:
        pass
    # Try to extract a JSON block
    extracted = _extract_json_block(s)
    if extracted is not None:
        return True, extracted
    return False, text


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: read env and log configuration. If OLLAMA_BASE_URL is missing
    # run in a developer-friendly "local mode" instead of failing the process.
    base = os.environ.get('OLLAMA_BASE_URL')
    model = os.environ.get('OLLAMA_MODEL')
    if not base:
        logging.warning(
            'OLLAMA_BASE_URL not set: starting in local mode. /chat will be limited or return a stub when OLLAMA_MODEL=mock.'
        )
        app.state.local_mode = True
    else:
        app.state.local_mode = False
    # Keep config on the app state for handlers to access
    # Normalize base: strip trailing slashes and common prefixes like /v1 or /api
    raw_base = base or 'http://127.0.0.1:11434'
    b = raw_base.rstrip('/')
    # remove trailing /v1, /api, or /v1/api (case-insensitive)
    b = re.sub(r'(/v1(/api)?|/api)$', '', b, flags=re.IGNORECASE)
    app.state.ollama_base = b or 'http://127.0.0.1:11434'
    app.state.ollama_model = model
    # Allow tests to override model per-request when this env var is set to 'true'
    allow_override = os.environ.get('OLLAMA_ALLOW_MODEL_OVERRIDE', 'false').lower() in ('1', 'true', 'yes')
    app.state.allow_model_override = allow_override
    logging.info(f'Ollama base URL: {app.state.ollama_base} (normalized from {base})')
    logging.info(f'Ollama model: {app.state.ollama_model}')
    logging.info(f'Ollama allow_model_override: {app.state.allow_model_override}')
    yield


app = FastAPI(lifespan=lifespan)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/chat')
def chat(payload: dict):
    prompt = payload.get('prompt', '')
    # Per-request UUID for correlation (create early so error responses include it)
    request_id = str(uuid.uuid4())

    # Per-request logging adapter for correlation (create early so it's usable everywhere)
    logger = logging.getLogger(__name__)
    adapter = logging.LoggerAdapter(logger, {'request_id': request_id})
    adapter.info('received /chat request')

    if not prompt:
        adapter.warning('missing prompt')
        return JSONResponse(status_code=400, content={"error": "missing prompt", "request_id": request_id})

    # Read configuration from the app state (set during lifespan)
    ollama_base = getattr(app.state, 'ollama_base', os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'))
    model = getattr(app.state, 'ollama_model', os.environ.get('OLLAMA_MODEL'))
    # Allow per-request override of the model when enabled (testing/CI)
    if getattr(app.state, 'allow_model_override', False):
        req_model = payload.get('model') if isinstance(payload, dict) else None
        if req_model:
            adapter.info('overriding model from request', extra={'requested_model': req_model})
            model = req_model

    # If the server started in local mode (no OLLAMA_BASE_URL), provide
    # developer-friendly behavior: either return a clear 503 explaining
    # the missing config, or, if `OLLAMA_MODEL=mock`, return a simple stub.
    if getattr(app.state, 'local_mode', False):
        if model and model.lower() in ('mock', 'local_stub'):
            adapter.info('local_mode: returning mock/stub response', extra={'attempt': 0})
            stub = {
                'lessonTitle': 'Local stub result',
                'objectives': ['This is a developer stub response'],
                'prompt_echo': prompt,
            }
            return JSONResponse(status_code=200, content={**stub, 'request_id': request_id})
        return JSONResponse(
            status_code=503,
            content={
                'error': 'no_model_configured',
                'message': 'OLLAMA_BASE_URL not set; server running in local mode. Set OLLAMA_BASE_URL to enable model calls, or set OLLAMA_MODEL=mock to use a local stub.',
                'request_id': request_id,
            },
        )

    if not model:
        adapter.error('no model configured')
        return JSONResponse(
            status_code=500,
            content={"error": "no_model_configured", "message": 'No agent configured; set OLLAMA_MODEL or GITHUB model env vars.', "request_id": request_id},
        )

    system_msg = (
        "You are a JSON-only responder. Return STRICT JSON only — no commentary, no analysis, no markdown, and no extra tokens. "
        "If you cannot produce valid JSON, return {\"error\":\"cannot_produce_json\",\"reason\":\"<brief reason>\"}."
    )

    body = {
        "stream": False,
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2, "num_predict": 1200, "stop": ["```"]},
    }

    # Configurable timeout and retry/backoff
    timeout = float(os.environ.get('OLLAMA_TIMEOUT', '60'))
    max_retries = int(os.environ.get('OLLAMA_MAX_RETRIES', '3'))
    backoff_factor = float(os.environ.get('OLLAMA_BACKOFF_FACTOR', '0.5'))

    adapter.info('start chat request', extra={'model': model})

    resp = None
    text = ''
    last_exc = None
    # Try multiple common endpoint paths in case the configured base uses a different prefix
    endpoint_paths = ['/api/chat', '/v1/api/chat']
    for attempt in range(1, max_retries + 1):
        for path in endpoint_paths:
            url = f"{ollama_base.rstrip('/')}{path}"
            try:
                adapter.info('calling ollama', extra={'attempt': attempt, 'url': url})
                resp = requests.post(url, json=body, timeout=timeout)
                resp.raise_for_status()
                # Prefer the text representation for fallback parsing
                text = resp.text or ''
                adapter.info('ollama call succeeded', extra={'attempt': attempt, 'status_code': resp.status_code, 'url': url})
                # Log a truncated raw response body for debugging/parsing validation
                try:
                    raw_preview = (resp.text or '')[:2000]
                    adapter.info('ollama raw response preview: %s', raw_preview)
                except Exception:
                    adapter.exception('failed to log raw response preview')
                break
            except RequestException as e:
                last_exc = e
                adapter.warning('call to %s failed: %s', url, e)
                # try next path or next attempt
                continue
        else:
            # inner loop didn't break -> all paths failed for this attempt
            if attempt == max_retries:
                adapter.exception('Ollama request failed after %d attempts', attempt)
                return JSONResponse(
                    status_code=502,
                    content={"error": "ollama_request_failed", "details": str(last_exc), "request_id": request_id},
                )
            sleep_t = backoff_factor * (2 ** (attempt - 1))
            adapter.warning('Ollama request attempt %d/%d failed; retrying in %.2fs', attempt, max_retries, sleep_t)
            time.sleep(sleep_t)
        # if we reached here and resp succeeded (inner break), break outer loop
        if resp is not None and resp.ok:
            break

    # Defensive: ensure we have some response text to examine
    if resp is None:
        adapter.error('no response object after retries')
        return JSONResponse(status_code=502, content={"error": "no_response", "request_id": request_id})

    # Attempt to parse JSON from the response body with robust fallbacks
    out_text = ''
    try:
        try:
            parsed = resp.json()
        except ValueError:
            # Not JSON; fall back to text
            parsed = None

        if parsed is None:
            out_text = text
        else:
            # parsed may already be the final structure
            if isinstance(parsed, dict):
                # Common shapes
                if 'output' in parsed:
                    out_val = parsed['output']
                    # If output is a string, try to parse it
                    if isinstance(out_val, str):
                        success, val = _try_parse_json_like(out_val)
                        if success:
                            return JSONResponse(status_code=200, content={**(val if isinstance(val, dict) else {'result': val}), "request_id": request_id})
                        out_text = out_val
                    else:
                        return JSONResponse(status_code=200, content={**(out_val if isinstance(out_val, dict) else {'result': out_val}), "request_id": request_id})
                elif 'choices' in parsed and parsed.get('choices'):
                    first = parsed['choices'][0]
                    # Try common nested shapes
                    msg = None
                    if isinstance(first, dict) and first.get('message'):
                        msg = first['message'].get('content')
                    elif isinstance(first, dict) and first.get('text'):
                        msg = first.get('text')
                    if msg:
                        success, val = _try_parse_json_like(msg)
                        if success:
                            return JSONResponse(status_code=200, content={**(val if isinstance(val, dict) else {'result': val}), "request_id": request_id})
                        out_text = msg
                    else:
                        out_text = json.dumps(parsed)
                elif parsed.get('message') and isinstance(parsed.get('message'), dict) and isinstance(parsed['message'].get('content'), str):
                    candidate = parsed['message'].get('content', '').strip()
                    success, val = _try_parse_json_like(candidate)
                    if success:
                        return JSONResponse(status_code=200, content={**(val if isinstance(val, dict) else {'result': val}), "request_id": request_id})
                    out_text = candidate
                else:
                    # Heuristic structured result
                    if 'lessonTitle' in parsed or 'objectives' in parsed:
                        return JSONResponse(status_code=200, content={**parsed, "request_id": request_id})
                    out_text = json.dumps(parsed)
            else:
                out_text = str(parsed)
    except Exception:
        # Ensure out_text is defined
        out_text = out_text or text
        adapter.exception('error while parsing model response')

    # Try to extract a JSON block from the textual output
    success, val = _try_parse_json_like(out_text)
    if success:
        return JSONResponse(status_code=200, content={**(val if isinstance(val, dict) else {'result': val}), "request_id": request_id})

    # Last resort: return structured error with raw text for debugging
    adapter.warning('unable to parse model output; returning raw for debugging')
    return JSONResponse(status_code=502, content={"error": "json_parse_failed", "raw": out_text, "request_id": request_id})


@app.post('/invoke')
async def invoke(req: Request):
    payload = await req.json()
    return chat(payload)


@app.post('/')
async def root_post(req: Request):
    payload = await req.json()
    return chat(payload)


@app.get('/diag')
def diag():
    import shutil, subprocess
    ollama_path = shutil.which('ollama')
    env_model = os.environ.get('OLLAMA_MODEL')
    env_base = os.environ.get('OLLAMA_BASE_URL')
    try:
        r = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        ollama_list = (r.stdout or '') + (r.stderr or '')
    except Exception as e:
        ollama_list = f'ERROR running ollama list: {e}'
    return {
        'OLLAMA_BASE_URL': env_base,
        'OLLAMA_MODEL': env_model,
        'which_ollama': ollama_path,
        'ollama_list': (ollama_list or '')[:2000],
    }
