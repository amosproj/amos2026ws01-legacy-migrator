param(
    [string]$ReferenceSource
)

$ErrorActionPreference = "Stop"
$useExport = -not $PSBoundParameters.ContainsKey("ReferenceSource")
if ($useExport) {
    $ReferenceSource = Join-Path $PSScriptRoot "backend/code-ingestion-pipeline/demo-data/step-06-full"
    foreach ($file in "snapshot-identity.json", "entities.jsonl", "relationships.jsonl", "sources.jsonl") {
        if (-not (Test-Path -LiteralPath (Join-Path $ReferenceSource $file) -PathType Leaf)) {
            throw "Demo export is missing $file in $ReferenceSource. Update your develop checkout. See SETUP.md."
        }
    }
}
$reference = (Resolve-Path -LiteralPath $ReferenceSource).Path
if (-not $useExport -and -not (Test-Path -LiteralPath (Join-Path $reference ".git"))) {
    throw "Reference checkout missing: $reference. See SETUP.md."
}
Get-Command docker, ollama -ErrorAction Stop | Out-Null

function Test-Docker {
    try {
        docker info 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-Ollama {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-Ready([scriptblock]$Probe, [string]$Service) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (& $Probe) { return }
        Start-Sleep -Seconds 1
    }
    throw "$Service did not become ready."
}

if (-not (Test-Docker)) {
    $desktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $desktop)) { throw "Start Docker Desktop first. See SETUP.md." }
    Start-Process -FilePath $desktop
    Wait-Ready { Test-Docker } "Docker"
}
docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose is required. See SETUP.md." }

$previous = @{
    REFERENCE_SOURCE = $env:REFERENCE_SOURCE
    OLLAMA_HOST = $env:OLLAMA_HOST
    LLM_NAME = $env:LLM_NAME
}
$compose = @("compose", "--project-name", "sunsettracker-tester-$PID", "-f", "docker-compose.tester.yml")
if ($useExport) {
    $compose += @("-f", "docker-compose.tester.export.yml")
}
$ollamaProcess = $null
$composeStarted = $false
Push-Location $PSScriptRoot
try {
    $env:REFERENCE_SOURCE = $reference
    $env:OLLAMA_HOST = "127.0.0.1:11434"
    if (-not (Test-Ollama)) {
        $ollamaProcess = Start-Process -FilePath "ollama" -ArgumentList "serve" -NoNewWindow -PassThru
        Wait-Ready { Test-Ollama } "Ollama"
    }
    if (-not $env:LLM_NAME) { $env:LLM_NAME = "qwen3.5:2b" }
    try {
        $modelRequest = @{ model = $env:LLM_NAME } | ConvertTo-Json -Compress
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/show" -Method Post -TimeoutSec 5 `
            -ContentType "application/json" -Body $modelRequest | Out-Null
    } catch {
        ollama pull $env:LLM_NAME
        if ($LASTEXITCODE -ne 0) { throw "Could not pull $env:LLM_NAME." }
    }

    if ($useExport) {
        Write-Host "Loading the saved step-06 export. Open http://localhost:3000 when the frontend starts."
    } else {
        Write-Host "Importing step-06 from Git. Open http://localhost:3000 when the frontend starts."
    }
    $imageOptions = @("--no-build")
    if (-not $env:SUNSETTRACKER_BACKEND_IMAGE -and -not $env:SUNSETTRACKER_FRONTEND_IMAGE) {
        $imageOptions += @("--pull", "always")
    }
    $composeStarted = $true
    docker @compose up @imageOptions
    if ($LASTEXITCODE -ne 0) { throw "Tester startup failed. See the Compose logs above." }
} finally {
    try {
        if ($composeStarted) { docker @compose down --volumes }
    } finally {
        if ($ollamaProcess) { Stop-Process -InputObject $ollamaProcess -ErrorAction SilentlyContinue }
        foreach ($entry in $previous.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value)
        }
        Pop-Location
    }
}
