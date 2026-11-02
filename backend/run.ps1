# Start the SunsetTracker backend plus a local Ollama server in Windows Terminal.
# One wt window, one tab per process. Closing the window stops them all, since each
# process is a child of its tab. Add a third tab here later for the frontend (Vite).

$ErrorActionPreference = "Stop"
$backendDir = $PSScriptRoot

$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }
$apiHost    = if ($env:HOST)        { $env:HOST }        else { "127.0.0.1" }
$apiPort    = if ($env:PORT)        { $env:PORT }        else { "8000" }
$model      = if ($env:LLM_NAME)    { $env:LLM_NAME }    else { "qwen3.5:0.8b" }

# Backend tab: point at the local Ollama server, sync deps, start uvicorn.
$backendCmd = "Set-Location '$backendDir'; " +
              "`$env:LLM_BASE_URL='http://127.0.0.1:$ollamaPort/v1'; " +
              "`$env:LLM_NAME='$model'; " +
              "`$env:LLM_EXTRA_BODY='{`\"think`\": false}'; " +
              "uv sync; " +
              "uv run uvicorn app.main:app --host $apiHost --port $apiPort"

wt -w new new-tab -t "Ollama" pwsh -NoExit -Command "ollama serve" `; `
   new-tab -t "Backend" pwsh -NoExit -Command $backendCmd