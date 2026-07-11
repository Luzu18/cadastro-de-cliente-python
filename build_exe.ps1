<#
build_exe.ps1

Cria um executável Windows (one-file) usando PyInstaller.

Uso (PowerShell):
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\build_exe.ps1

Opções:
  -Rebuild  : Limpa pastas de build/dist antes de gerar.

Obs: o script cria/usa a virtualenv `.venv` no diretório do projeto.
#>

param(
    [switch]$Rebuild = $false
)

$venvPath = ".\.venv"
if (-not (Test-Path $venvPath)) {
    python -m venv .venv
}

# Ativa a venv (PowerShell)
. .\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

if ($Rebuild) {
    Write-Host "Limpando diretórios de build e dist..."
    Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
    Remove-Item -Force .\CadastroCliente.spec -ErrorAction SilentlyContinue
}

Write-Host "Gerando executável com PyInstaller (incluindo banco os_database.db)..."
# Incluir o arquivo SQLite para que o exe já contenha o banco com tabelas
pyinstaller --onefile --noconsole --add-data "os_database.db;." --name CadastroCliente cliente_manager.py

if (Test-Path .\dist\CadastroCliente.exe) {
    Write-Host "Build completo. Executável em: .\dist\CadastroCliente.exe"
} else {
    Write-Host "Build finalizado, verifique a saída do PyInstaller para erros." -ForegroundColor Yellow
}
