#!/usr/bin/env python3
"""Run a command that emits model output, extract JSON, validate against a schema,
and optionally retry with a repair command when validation fails.

Usage examples:
  python scripts/ollama_output_wrapper.py --cmd "ollama run mymodel --prompt '... '" \
    --schema-file schemas/output_schema.json --max-retries 2 \
    --repair-cmd "ollama run mymodel --prompt 'Fix the JSON only. Error: {error}\nOriginal:\n{output}'"

This wrapper is intentionally generic: pass any shell command as `--cmd` and
optionally provide a `--repair-cmd` template. The `--repair-cmd` string may
contain the placeholders `{error}` and `{output}` which will be filled with the
validation error text and original model output respectively.
"""

import argparse
import json
import subprocess
import sys
from typing import Optional

try:
    import jsonschema
    from jsonschema import validate
except Exception:  # pragma: no cover - optional dependency
    jsonschema = None


def run_shell_command(cmd: str, timeout: Optional[int] = None) -> str:
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    out = proc.stdout or ""
    err = proc.stderr or ""
    # combine stdout+stderr in a predictable way for repair prompts
    combined = out.strip()
    if err.strip():
        combined = combined + "\n" + err.strip() if combined else err.strip()
    return combined


def extract_json(text: str) -> Optional[str]:
    # Try to find the first JSON object or array in the text.
    # This is a pragmatic extractor: looks for balanced braces/brackets.
    text = text.strip()
    if not text:
        return None

    # If the entire text is JSON, return it quickly.
    try:
        json.loads(text)
        return text
    except Exception:
        pass

    # Find a JSON object starting at first '{'
    obj_start = text.find('{')
    arr_start = text.find('[')
    starts = [i for i in (obj_start, arr_start) if i != -1]
    if not starts:
        return None
    start = min(starts)

    # Attempt to find a matching closing bracket by scanning and counting.
    stack = []
    pairs = {'{': '}', '[': ']'}
    for i in range(start, len(text)):
        ch = text[i]
        if ch in '{[':
            stack.append(pairs[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                candidate = text[start:i+1]
                try:
                    json.loads(candidate)
                    return candidate
                except Exception:
                    # not valid JSON, keep scanning for next candidate
                    pass
    return None


def validate_json(instance: dict, schema: Optional[dict]) -> Optional[str]:
    if schema is None:
        # No schema provided; consider successful if instance is JSON-parsable
        return None
    if jsonschema is None:
        return "jsonschema not installed"
    try:
        validate(instance=instance, schema=schema)
        return None
    except Exception as e:
        return str(e)


def load_schema(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load schema {path}: {e}", file=sys.stderr)
        return None


def main():
    p = argparse.ArgumentParser(description="Wrapper: run command, extract+validate JSON, retry with repair command")
    p.add_argument('--cmd', required=True, help='Shell command to run that produces model output')
    p.add_argument('--schema-file', help='Path to a JSON schema file to validate output against')
    p.add_argument('--max-retries', type=int, default=2, help='Number of repair attempts')
    p.add_argument('--repair-cmd', help='Shell command template to run on validation failure. May include {error} and {output}')
    p.add_argument('--timeout', type=int, default=30, help='Command timeout seconds')
    args = p.parse_args()

    schema = load_schema(args.schema_file)

    attempt = 0
    last_output = ''
    while True:
        attempt += 1
        out = run_shell_command(args.cmd, timeout=args.timeout)
        last_output = out

        json_text = extract_json(out)
        if json_text:
            try:
                obj = json.loads(json_text)
            except Exception as e:
                validation_error = f'JSON parse error: {e}'
                obj = None
        else:
            validation_error = 'No JSON found in output'
            obj = None

        if obj is not None:
            schema_err = validate_json(obj, schema)
            if schema_err is None:
                # Success: print only the JSON (compact) and exit 0
                print(json.dumps(obj, ensure_ascii=False))
                sys.exit(0)
            else:
                validation_error = schema_err

        # If we reach here, validation failed
        print(f"Attempt {attempt}: validation failed: {validation_error}", file=sys.stderr)

        if attempt > args.max_retries or not args.repair_cmd:
            print("Final model output (raw):", file=sys.stderr)
            print(last_output, file=sys.stderr)
            sys.exit(2)

        # Prepare repair command
        try:
            repair_cmd = args.repair_cmd.format(error=validation_error, output=last_output)
        except Exception:
            repair_cmd = args.repair_cmd

        print(f"Running repair command (attempt {attempt})...", file=sys.stderr)
        args.cmd = repair_cmd


if __name__ == '__main__':
    main()
