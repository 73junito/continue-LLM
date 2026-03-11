# Ultra-Continue VS Code Cheat Sheet

Quick commands and step-by-step tests to verify models and features.

## Environment

PowerShell (set once per session or add to workspace settings):

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

(We added this to the workspace settings under `.vscode/settings.json`.)

## Verify Ollama + Models

```powershell
ollama ps
ollama list
ollama run starcoder2:3b "print('Hello, World!')"
```

Expect a short code response from `starcoder2:3b`.

## 1 — Autocomplete (StarCoder2)

1. Open any `.py` file.
2. Add this skeleton:

```python
def add_numbers(a, b):
```

1. Wait for inline suggestions or press `Ctrl+Space`.
2. Expected suggestion:

```python
    return a + b
```

Notes: If suggestions don’t appear, ensure the Continue extension (or whichever extension integrates models) is enabled and VS Code was reloaded after workspace env changes.

## 2 — Slash Command: `explain` (Llama3)

1. Select code, e.g.: `result = add_numbers(5, 7)`.
2. Trigger the Continue slash command `/explain` (or pick from the extension command palette).
3. Expected: a clear explanation of the selected code from Llama3.

## 3 — Multi-file Refactor: `refactor` (DeepSeek-Coder)

1. Open a repo with at least two files referencing the same function.
2. Select the function definition or name.
3. Trigger `/refactor` and specify the desired change (rename or signature change).
4. Preview changes and apply. Verify all references updated.

## 4 — Generate Unit Tests: `tests` (StarCoder2)

1. Select the function to test.
2. Trigger `/tests`.
3. Expected output — a unit test file skeleton (e.g., `tests/test_module.py`) you can review and run.

## Quick Troubleshooting

- If pulls or runs fail with timeouts: ensure Ollama daemon is running (`ollama serve`) and `OLLAMA_HOST` points to `http://127.0.0.1:11434`.
- Check models with `ollama list`.
- If CLI flags differ, run `ollama run --help` to confirm usage on your version.
- Restart VS Code after workspace `settings.json` changes so terminals and extensions pick up `OLLAMA_HOST`.

## Extra Commands

- Check server logs (in the server shell running `ollama serve`) for startup errors.
- To reload VS Code window: `Developer: Reload Window` (Command Palette).

---

If you want, I can also:

- Open the template workspace in VS Code now.
- Run the autocomplete/refactor tests automatically (I can drive simple examples).
- Produce a shorter printable 1-page checklist for quick runs.
