@echo off
start "LibraAI Python Backend" cmd /k "python app.py"
cd frontend
npm install
npm run dev
