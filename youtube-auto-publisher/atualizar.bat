@echo off
echo ========================================
echo    YouTube Auto Publisher - Atualizador
echo ========================================
echo.
echo [1/3] Baixando atualizacoes do GitHub...
git pull
echo.
echo [2/3] Instalando dependencias Python...
py -m pip install -r requirements.txt
echo.
echo [3/3] Pronto! Execute agora:
echo    python main.py --topic natureza --dry-run
echo.
pause
