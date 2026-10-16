$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# JianzhouCat.spec builds a slim one-file exe (no OpenGL/QML/network parts).
python -m PyInstaller --noconfirm --clean JianzhouCat.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
