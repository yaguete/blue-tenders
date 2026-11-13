#!/bin/bash

# Arranca la API (FastAPI) y la interfaz (Next.js) de blue-tender.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
set -m

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

mkdir -p logs

running() {
  local pidfile="logs/$1.pid"
  [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

port_busy() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

if running backend || running frontend; then
  echo -e "${YELLOW}Ya hay servidores de este repo en marcha.${NC}"
  echo "Para pararlos: ./stop.sh"
  [ -f logs/backend.pid ] && echo "   API:       PID $(cat logs/backend.pid)"
  [ -f logs/frontend.pid ] && echo "   Interfaz:  PID $(cat logs/frontend.pid)"
  exit 1
fi

if port_busy 8000 || port_busy 3000; then
  echo -e "${YELLOW}El puerto 8000 o el 3000 ya está ocupado por otro proceso.${NC}"
  echo "Mira quién es con: lsof -nP -iTCP:8000 -sTCP:LISTEN"
  echo "                   lsof -nP -iTCP:3000 -sTCP:LISTEN"
  exit 1
fi

echo "Arrancando blue-tender..."
echo ""

echo -e "${BLUE}API (FastAPI)...${NC}"
(
  cd "$ROOT/backend"
  exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) > "$ROOT/logs/backend.log" 2>&1 &
echo $! > logs/backend.pid
disown

echo -e "${BLUE}Interfaz (Next.js)...${NC}"
(
  cd "$ROOT/frontend"
  exec npm run dev -- --port 3000
) > "$ROOT/logs/frontend.log" 2>&1 &
echo $! > logs/frontend.pid
disown

echo ""
echo "Esperando a que respondan..."

backend_up=0
frontend_up=0
for _ in $(seq 1 40); do
  if [ "$backend_up" -eq 0 ] && curl -sf http://127.0.0.1:8000/health >/dev/null; then
    backend_up=1
  fi
  if [ "$frontend_up" -eq 0 ] && curl -sf -o /dev/null http://127.0.0.1:3000; then
    frontend_up=1
  fi
  if [ "$backend_up" -eq 1 ] && [ "$frontend_up" -eq 1 ]; then
    break
  fi
  sleep 0.5
done

echo ""
if [ "$backend_up" -eq 1 ] && [ "$frontend_up" -eq 1 ]; then
  echo -e "${GREEN}Servidores arrancados:${NC}"
else
  echo -e "${YELLOW}Alguno no ha respondido a tiempo. Revisa los logs.${NC}"
fi
echo ""
echo "   API:       http://127.0.0.1:8000"
echo "   Interfaz:  http://localhost:3000"
echo ""
echo "Logs:"
echo "   logs/backend.log"
echo "   logs/frontend.log"
echo ""
echo "Para pararlos: ./stop.sh"
echo ""

if [ "$backend_up" -eq 0 ]; then
  echo "--- últimas líneas de logs/backend.log ---"
  tail -n 20 logs/backend.log
fi
if [ "$frontend_up" -eq 0 ]; then
  echo "--- últimas líneas de logs/frontend.log ---"
  tail -n 20 logs/frontend.log
fi

if [ "$backend_up" -eq 0 ] || [ "$frontend_up" -eq 0 ]; then
  exit 1
fi
