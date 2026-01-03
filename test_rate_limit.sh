#!/bin/bash
SESSION_ID="bfd6018a-11f2-4d6a-a86e-dae03a6c3e52"
i=1
while [ $i -le 32 ]; do
  result=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d "{\"session_id\": \"$SESSION_ID\", \"query\": \"Bitcoin price\"}")
  http_code=$(echo "$result" | tail -1)
  echo "Request $i: HTTP $http_code"
  if [ "$http_code" = "429" ]; then
    echo "Rate limited! Response body:"
    echo "$result" | head -n -1
    break
  fi
  i=$((i + 1))
done
