# Start the SunsetTracker backend, a local Ollama server and the frontend in
# Windows Terminal. One wt window, one tab per process. Closing the window stops
# them all, since each process is a child of its tab.

$ErrorActionPreference = "Stop"
$backendDir  = $PSScriptRoot
$frontendDir = Join-Path (Split-Path $backendDir -Parent) "frontend"

$ollamaPort = if ($env:OLLAMA_PORT) { $env:OLLAMA_PORT } else { "11434" }
$apiHost    = if ($env:HOST)        { $env:HOST }        else { "127.0.0.1" }
$apiPort    = if ($env:PORT)        { $env:PORT }        else { "8000" }
$model      = if ($env:LLM_NAME)    { $env:LLM_NAME }    else { "qwen3.5:0.8b" }

# Fail early when the local model is missing; skipped for remote providers.
$llmBaseUrl = if ($env:LLM_BASE_URL) { $env:LLM_BASE_URL } else { "http://127.0.0.1:$ollamaPort/v1" }
if ($llmBaseUrl -match "127\.0\.0\.1|localhost") {
    $pulled = & ollama list 2>$null | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] }
    if ($pulled -notcontains $model) {
        Write-Error "model '$model' is not pulled. Run: ollama pull $model"
        exit 1
    }
}

# Backend tab: point at the local Ollama server, sync deps, start uvicorn.
$backendCmd = "Set-Location '$backendDir'; " +
              "`$env:LLM_BASE_URL='http://127.0.0.1:$ollamaPort/v1'; " +
              "`$env:LLM_NAME='$model'; " +
              "`$env:LLM_EXTRA_BODY='{`\"think`\": false}'; " +
              "uv sync; " +
              "uv run uvicorn app.main:app --host $apiHost --port $apiPort"

# Frontend tab: install deps if needed, build, then preview.
$frontendCmd = "Set-Location '$frontendDir'; " +
               "if (-not (Test-Path node_modules)) { npm install }; " +
               "npm run build; " +
               "npm run preview"

wt -w new new-tab -t "Ollama" pwsh -NoExit -Command "ollama serve" `; `
   new-tab -t "Backend" pwsh -NoExit -Command $backendCmd `; `
   new-tab -t "Frontend" pwsh -NoExit -Command $frontendCmd