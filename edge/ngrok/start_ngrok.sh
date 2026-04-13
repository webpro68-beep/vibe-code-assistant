#!/usr/bin/env bash
set -euo pipefail
CONFIG_FILE="${1:-./edge/ngrok/ngrok.example.yml}"
ngrok start --all --config "$CONFIG_FILE"
