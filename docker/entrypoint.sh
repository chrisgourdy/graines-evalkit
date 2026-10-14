#!/bin/sh
# Modes: cli <args> | api | worker <project> <agent> [profile] | scheduler <plan.yaml>
set -eu
mode="${1:-cli}"; [ "$#" -gt 0 ] && shift
evalkit db migrate --data-dir "${EVALKIT_DATA_DIR}" >/dev/null
case "$mode" in
  cli)       exec evalkit "$@" ;;
  api)       exec evalkit api serve --host "${EVALKIT_API_HOST:-0.0.0.0}" --port "${EVALKIT_API_PORT:-8765}" ;;
  worker)    project="$1"; agent="$2"; profile="${3:-standard}"
             exec evalkit run "${EVALKIT_PROJECTS_DIR}/${project}" --agent "$agent" --profile "$profile" --data-dir "${EVALKIT_DATA_DIR}" ;;
  scheduler) echo "scheduler mode arrives in Phase 7 (docs/ROADMAP.md)" >&2; exit 64 ;;
  *)         exec evalkit "$mode" "$@" ;;
esac
