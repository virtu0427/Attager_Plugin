#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_CARDS_DIR="$SCRIPT_DIR/../../../../agent_cards"

echo "Looking for agent cards in: $AGENT_CARDS_DIR"

shopt -s nullglob
files=("$AGENT_CARDS_DIR"/*.json)
if [ ${#files[@]} -eq 0 ]; then
  echo "❌ No JSON files found in $AGENT_CARDS_DIR"
  exit 1
fi

for file in "${files[@]}"; do
  echo "Registering agent from $file..."
  curl -X POST "http://localhost:8000/agents/register" \
       -H "Content-Type: application/json" \
       -d "@$file"
  echo -e "\n"
done

echo "✅ All agents from $AGENT_CARDS_DIR registered."

# Assert 1 parameter is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <file>"
    exit 1
fi

file=$1

curl -X POST "http://localhost:8000/agents/register" -H "Content-Type: application/json" -d @$file
