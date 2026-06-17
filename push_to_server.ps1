# push_to_server.ps1
# Run this from your Windows machine to copy the project to the Linux server
# Usage: Right-click -> Run with PowerShell, or run in terminal

$SERVER = "jason@192.168.11.68"
$REMOTE = "~/qa-report"
$LOCAL  = $PSScriptRoot

Write-Host "=== Pushing project to $SERVER ===" -ForegroundColor Cyan

# Create remote folder
ssh $SERVER "mkdir -p $REMOTE"

# Copy all project files (excludes the db file and key files for safety)
$files = @(
    "app.py",
    "config.py",
    "critiera.py",
    "dashboard.py",
    "db.py",
    "engine.py",
    "file_parser.py",
    "requirements.txt",
    "deploy.sh"
)

foreach ($file in $files) {
    $src = Join-Path $LOCAL $file
    if (Test-Path $src) {
        Write-Host "  Copying $file..." -ForegroundColor Gray
        scp $src "${SERVER}:${REMOTE}/${file}"
    }
}

# Copy .streamlit config folder
Write-Host "  Copying .streamlit/config.toml..." -ForegroundColor Gray
ssh $SERVER "mkdir -p $REMOTE/.streamlit"
scp "$LOCAL\.streamlit\config.toml" "${SERVER}:${REMOTE}/.streamlit/config.toml"

Write-Host ""
Write-Host "=== Files copied! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Now SSH in and run the deploy script:" -ForegroundColor Yellow
Write-Host "  ssh $SERVER" -ForegroundColor White
Write-Host "  cd qa-report && bash deploy.sh" -ForegroundColor White
Write-Host ""
Write-Host "Then copy your API keys:" -ForegroundColor Yellow
Write-Host "  scp api_key.txt ${SERVER}:${REMOTE}/api_key.txt" -ForegroundColor White
Write-Host "  scp deepgram_key.txt ${SERVER}:${REMOTE}/deepgram_key.txt" -ForegroundColor White
