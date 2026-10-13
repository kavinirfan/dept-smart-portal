@echo off
REM One-command start: installs dependencies, builds the web app, seeds demo data, runs the server.
cd /d "%~dp0"
python -m pip install -q -r backend\requirements.txt || exit /b 1
pushd frontend
call npm install --silent || exit /b 1
call npm run build --silent || exit /b 1
popd
pushd backend
python -m app.seed
echo.
echo Portal running at http://localhost:8000  (demo password: portal123)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
popd
