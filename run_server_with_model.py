import os
import uvicorn

# Set Ollama model for testing
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_MODEL", "mistral:7b")

if __name__ == '__main__':
    from autolearnpro_agent import server as server_mod
    app = getattr(server_mod, 'app')
    uvicorn.run(app, host='127.0.0.1', port=8001)
