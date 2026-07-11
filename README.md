## Gerar executável Windows (PyInstaller)

Este projeto é uma aplicação desktop em Tkinter. Para distribuir um executável Windows para usuários finais, recomendo empacotar com o PyInstaller em um único arquivo (`--onefile`).

Passos rápidos:

1. Abra PowerShell na pasta do projeto.
2. Permita execução de scripts temporariamente (se necessário):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

3. Rode o script de build (ele cria/usa `.venv`, instala dependências e PyInstaller):

```powershell
.\build_exe.ps1
```

4. O executável ficará em `dist\CadastroCliente.exe`.

Opções e dicas:
- Para forçar uma limpeza antes do build, rode: `.\build_exe.ps1 -Rebuild`
- Se quiser um ícone, gere um `app.ico` e altere a linha do PyInstaller para: `pyinstaller --onefile --noconsole --icon=app.ico --name CadastroCliente cliente_manager.py`
- Teste o executável em uma máquina limpa (ou dentro de uma VM) para garantir que todas as dependências foram incluídas.
- Para criar um instalador (.msi/.exe) amigável, use ferramentas como Inno Setup ou NSIS sobre o executável resultante.

Problemas comuns:
- Antivírus podem sinalizar executáveis recém-gerados; assinar digitalmente reduz falsos positivos.
- Se o PDF não for gerado, verifique se `reportlab` está instalado no ambiente usado para build.

Se quiser, eu posso:
- Gerar o executável aqui (vai abrir processo de build, mas sem abrir a GUI).
- Criar um instalador Inno Setup básico.
