#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HEADLESS_BINARY:=$PWD/.build/midi-headless-engine}"
: "${ENGINE_SOCKET:=${XDG_RUNTIME_DIR:-/tmp}/midi-human-looper-$UID.sock}"
: "${EDITOR_BIND:=127.0.0.1}"
: "${EDITOR_PORT:=8765}"
: "${PATCH_DIR:=${XDG_DATA_HOME:-$HOME/.local/share}/midi-human-looper}"
mode=(--jack); [[ "${MOCK_MIDI:-0}" == 1 ]] && mode=()
[[ "${DEMO_PATCH:-0}" == 1 ]] && mode+=(--demo)
[[ -n "${MIDI_INPUT:-}" ]] && mode+=(--input "$MIDI_INPUT")
[[ -n "${MIDI_OUTPUT:-}" ]] && mode+=(--output "$MIDI_OUTPUT")
"$HEADLESS_BINARY" midi_human_looper.jsfx "$ENGINE_SOCKET" "${mode[@]}" & engine_pid=$!
cleanup(){ kill -TERM "$engine_pid" 2>/dev/null || true; wait "$engine_pid" 2>/dev/null || true; }
trap cleanup EXIT
for ((attempt=0;attempt<200;attempt++));do
  [[ -S "$ENGINE_SOCKET" ]] && break
  kill -0 "$engine_pid" 2>/dev/null || { wait "$engine_pid";exit 1; }
  sleep .1
done
[[ -S "$ENGINE_SOCKET" ]] || { echo 'Engine startup timed out' >&2;exit 1; }
web=(--socket "$ENGINE_SOCKET" --bind "$EDITOR_BIND" --port "$EDITOR_PORT" --patch-dir "$PATCH_DIR")
[[ -n "${EDITOR_TOKEN_FILE:-}" ]] && web+=(--token-file "$EDITOR_TOKEN_FILE")
python3 headless/server.py "${web[@]}"
