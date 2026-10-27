@echo off
rem Gera o executável do Tradutor de Mangá para Windows.
rem Resultado: build\dist\TradutorManga\TradutorManga.exe
rem Se o Inno Setup estiver instalado, gera também o instalador em build\dist.
setlocal
cd /d "%~dp0.."

echo [1/3] Instalando dependencias...
python -m pip install -r requirements.txt -r build\requirements-interface.txt || goto erro

echo [2/3] Gerando o executavel...
python -m PyInstaller --noconfirm --clean --distpath build\dist --workpath build\temp build\tradutor_manga.spec || goto erro

echo [3/3] Gerando o instalador...
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% build\instalador.iss || goto erro
) else (
    echo Inno Setup nao encontrado: pulei o instalador. O programa ja esta em build\dist\TradutorManga
)

echo.
echo Pronto! Abra build\dist\TradutorManga\TradutorManga.exe
pause
exit /b 0

:erro
echo.
echo Falhou. Veja a mensagem acima.
pause
exit /b 1
