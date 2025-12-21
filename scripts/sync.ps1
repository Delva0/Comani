param (
    [string]$SERVER_IP = "79.160.189.79",
    [string]$SERVER_PORT = "12801",
    [string]$REMOTE_SRC = "/workspace/ComfyUI/user/hy1004_88a21f9c-cfdb-4c7e-8413-ad874fbb4fef/workflows/*.json",
    [string]$LOCAL_BASE = "C:\D\AI_Gen"
)

$DATE_STR = Get-Date -Format "yyyy-MM-dd"
$TARGET_DIR = Join-Path $LOCAL_BASE $DATE_STR

if (-not (Test-Path $TARGET_DIR)) {
    New-Item -ItemType Directory -Path $TARGET_DIR | Out-Null
}

$scpArgs = "-P", $SERVER_PORT, "root@${SERVER_IP}:${REMOTE_SRC}", "$TARGET_DIR\"
scp @scpArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "Success: $TARGET_DIR" -ForegroundColor Green
} else {
    Write-Host "Error" -ForegroundColor Red
}
