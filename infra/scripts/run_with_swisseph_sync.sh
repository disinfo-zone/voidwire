#!/bin/sh
set -eu

SWISSEPH_EPHE_PATH="${SWISSEPH_EPHE_PATH:-/opt/swisseph/ephe}"
SWISSEPH_EPHE_REF="${SWISSEPH_EPHE_REF:-master}"
SWISSEPH_SYNC_INTERVAL_SECONDS="${SWISSEPH_SYNC_INTERVAL_SECONDS:-86400}"

sync_once() {
  python infra/scripts/fetch_swisseph_asteroids.py \
    --dest "${SWISSEPH_EPHE_PATH}" \
    --ref "${SWISSEPH_EPHE_REF}" \
    --if-newer || echo "Swiss ephe sync failed (continuing)."
}

start_sync_loop() {
  if [ "${SWISSEPH_SYNC_INTERVAL_SECONDS}" = "0" ]; then
    return 0
  fi

  (
    while true; do
      sleep "${SWISSEPH_SYNC_INTERVAL_SECONDS}"
      sync_once
    done
  ) &
  SWISSEPH_SYNC_PID=$!
}

stop_sync_loop() {
  if [ -n "${SWISSEPH_SYNC_PID:-}" ]; then
    kill "${SWISSEPH_SYNC_PID}" 2>/dev/null || true
    wait "${SWISSEPH_SYNC_PID}" 2>/dev/null || true
  fi
}

if [ "$#" -eq 0 ]; then
  echo "run_with_swisseph_sync.sh requires a command to run." >&2
  exit 2
fi

sync_once
start_sync_loop

"$@" &
MAIN_PID=$!

on_signal() {
  kill "${MAIN_PID}" 2>/dev/null || true
  stop_sync_loop
}

trap on_signal INT TERM

wait "${MAIN_PID}"
STATUS=$?
stop_sync_loop
exit "${STATUS}"
