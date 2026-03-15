import os
import uvicorn

# Ensure Ollama base is present for the server process
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

if __name__ == '__main__':
    # Import the FastAPI app from the package
    from autolearnpro_agent import server as server_mod
    app = getattr(server_mod, 'app')
    uvicorn.run(app, host='127.0.0.1', port=8000)
