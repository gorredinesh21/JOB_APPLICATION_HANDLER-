#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
  echo "Usage: $0 <dev|prod>"
  exit 2
fi

echo "Starting ${ENVIRONMENT} deployment for job application pipeline"

case "$ENVIRONMENT" in
  dev)
    echo "Development deploy placeholder"
    echo "Add your dev server sync/restart commands here."
    ;;
  prod)
    echo "Production deploy placeholder"
    echo "Add your production server sync/restart commands here."
    ;;
esac

echo "${ENVIRONMENT} deployment hook completed"
