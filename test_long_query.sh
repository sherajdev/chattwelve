#!/bin/bash
# Generate a query longer than 5000 characters
LONG_QUERY=$(head -c 5100 /dev/zero | tr '\0' 'a')
curl -s -w "\nHTTP_CODE: %{http_code}" -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"b0171dc8-63dc-4731-b12d-d711acd1f48c\", \"query\": \"$LONG_QUERY\"}"
