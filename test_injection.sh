#!/bin/bash
# Test SQL injection prevention
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "b0171dc8-63dc-4731-b12d-d711acd1f48c", "query": "price of AAPL; DROP TABLE sessions;--"}'
