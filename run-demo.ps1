# Starts the whole KORA site locally with the demo data: database, backend, frontend.
#   powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
# Safe to run again at any time: it only starts what is not already running.
# Add -Reset to wipe the demo database and fill it again with fresh dates.
param([switch]$Reset)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$py = Join-Path $backend '.venv\Scripts\python.exe'
$container = 'kora-review-db'
$dbUrl = 'postgresql+asyncpg://kora:kora@127.0.0.1:5440/kora_demo'

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nSTOP: $text" -ForegroundColor Red; exit 1 }
function Listening($port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect('127.0.0.1', $port); return $true } catch { return $false } finally { $c.Close() }
}

if (-not (Test-Path $py)) { Fail "Backend environment missing. Run once:  cd backend ; uv sync" }
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) { Fail "Frontend packages missing. Run once:  cd frontend ; npm install" }

# 1. Docker -------------------------------------------------------------------------------------
Step 'Docker'
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $app = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $app)) { Fail 'Docker Desktop is not installed.' }
    Write-Host 'Starting Docker Desktop (this can take a minute)...'
    Start-Process $app
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Seconds 3
        docker info *> $null
        $ready = ($LASTEXITCODE -eq 0)
    }
    if (-not $ready) { Fail 'Docker did not start. Open Docker Desktop manually and run this again.' }
}
Write-Host 'Docker is running.'

# 2. Database container -------------------------------------------------------------------------
Step "Database container ($container)"
$exists = docker ps -a --filter "name=^/$container$" --format '{{.Names}}'
if (-not $exists) {
    docker run -d --name $container -p 127.0.0.1:5440:5432 -e POSTGRES_USER=kora -e POSTGRES_PASSWORD=kora -e POSTGRES_DB=kora postgres:17 | Out-Null
} else {
    $running = docker ps --filter "name=^/$container$" --format '{{.Names}}'
    if (-not $running) { docker start $container | Out-Null }
}
$up = $false
for ($i = 0; $i -lt 30 -and -not $up; $i++) {
    docker exec $container pg_isready -U kora *> $null
    $up = ($LASTEXITCODE -eq 0)
    if (-not $up) { Start-Sleep -Seconds 2 }
}
if (-not $up) { Fail 'The database did not become ready.' }
Write-Host 'Database is ready.'

# 3. Demo data ----------------------------------------------------------------------------------
Step 'Demo data (kora_demo)'
$env:KORA_ENVIRONMENT = 'local'
$env:KORA_DATABASE_URL = $dbUrl
if ($Reset -and (Listening 8000)) { Fail 'Stop the backend (port 8000) before using -Reset.' }
if ($Reset) { docker exec $container psql -U kora -d postgres -c 'DROP DATABASE IF EXISTS kora_demo' | Out-Null }
$has = docker exec $container psql -U kora -d postgres -At -c "SELECT 1 FROM pg_database WHERE datname='kora_demo'"
$fresh = -not $has
if ($fresh) { docker exec $container psql -U kora -d postgres -c 'CREATE DATABASE kora_demo' | Out-Null }
Push-Location $backend
try {
    & $py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Fail 'Database migration failed.' }
    if ($fresh) {
        Write-Host 'Filling the demo database (about a minute)...'
        & $py scripts\seed_demo.py $dbUrl
        if ($LASTEXITCODE -ne 0) { Fail 'Seeding failed.' }
    } else {
        Write-Host 'Demo data already there (use -Reset for fresh dates).'
    }
} finally { Pop-Location }

# 4. Backend ------------------------------------------------------------------------------------
Step 'Backend (http://127.0.0.1:8000)'
if (Listening 8000) {
    Write-Host 'Something already answers on port 8000; not starting another.' -ForegroundColor Yellow
    Write-Host 'If that is an OLD backend it may use the wrong database (backend\.env points at a cloud one). Close it and run this again.' -ForegroundColor Yellow
} else {
    $cmd = "`$env:KORA_ENVIRONMENT='local'; `$env:KORA_DATABASE_URL='$dbUrl'; Set-Location '$backend'; `$host.UI.RawUI.WindowTitle='KORA backend'; & '$py' -m uvicorn kora_api.main:app --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $cmd | Out-Null
    for ($i = 0; $i -lt 90 -and -not (Listening 8000); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Listening 8000)) { Fail 'The backend did not start. Look at its window for the error.' }
    Write-Host 'Backend is up.'
}

# 5. Frontend -----------------------------------------------------------------------------------
Step 'Frontend (http://localhost:5173)'
if (Listening 5173) {
    Write-Host 'The frontend is already running.'
} else {
    $cmd = "Set-Location '$frontend'; `$host.UI.RawUI.WindowTitle='KORA frontend'; npm run dev"
    Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $cmd | Out-Null
    for ($i = 0; $i -lt 60 -and -not (Listening 5173); $i++) { Start-Sleep -Seconds 1 }
}

Start-Process 'http://localhost:5173'
Write-Host "`nReady.  http://localhost:5173" -ForegroundColor Green
Write-Host 'Sign in with  omar / nasser / sultan / khaled / hind / admin   password: Kora-Demo-2026'
Write-Host 'To stop: close the two windows (KORA backend, KORA frontend).'
