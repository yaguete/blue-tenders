#!/bin/bash

# Para la API y la interfaz arrancadas por start.sh.
# Solo toca los PID de este repo: no mata otros `next dev` de la máquina.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Parando servidores..."
echo ""

kill_tree() {
  local pid="$1"
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stop_one() {
  local name="$1"
  local pidfile="logs/${name}.pid"
  if [ ! -f "$pidfile" ]; then
    echo "No hay PID de ${name}"
    return
  fi
  local pid
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    kill -- -"$pid" 2>/dev/null || kill_tree "$pid"
    local _
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "${name} parado (PID: ${pid})"
  else
    echo "${name} ya estaba parado"
  fi
  rm -f "$pidfile"
}

stop_one backend
stop_one frontend

echo ""
echo "Servidores parados"
