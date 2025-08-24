#!/bin/bash

# Admin API Endpoints Test Script
# Tests all 24 admin endpoints comprehensively

API_BASE="http://localhost:8000/api/v1/admin"
API_KEY="ak_4KcFgWtgWPy7U1jG3E2N8b31szi5pxBFQ4BKOvc873o"

echo "=== bin2nlp Admin Endpoints Testing ==="
echo "Testing all 24 admin endpoints..."
echo

# Headers for authenticated requests
AUTH_HEADER="Authorization: Bearer $API_KEY"

# Test 1: POST /api-keys (Create API Key)
echo "1. POST /api-keys - Create API Key"
curl -s -X POST "$API_BASE/api-keys" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "tier": "standard", "permissions": ["read"]}' | python3 -m json.tool
echo

# Test 2: GET /api-keys/{user_id} (List User API Keys)
echo "2. GET /api-keys/{user_id} - List User API Keys"
curl -s -X GET "$API_BASE/api-keys/test_user" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 3: DELETE /api-keys/{user_id}/{key_id} (Delete API Key)
echo "3. DELETE /api-keys/{user_id}/{key_id} - Delete API Key (will create one first)"
# First create a key to delete
KEY_RESPONSE=$(curl -s -X POST "$API_BASE/api-keys" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "delete_test", "tier": "basic", "permissions": ["read"]}')
KEY_ID=$(echo "$KEY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['key_id'])")
echo "Created key $KEY_ID for deletion test"
curl -s -X DELETE "$API_BASE/api-keys/delete_test/$KEY_ID" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 4: GET /stats (System Stats)
echo "4. GET /stats - System Stats"
curl -s -X GET "$API_BASE/stats" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 5: GET /rate-limits/{user_id} (Rate Limit Status)
echo "5. GET /rate-limits/{user_id} - Rate Limit Status"
curl -s -X GET "$API_BASE/rate-limits/test_user" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 6: GET /config (System Configuration)
echo "6. GET /config - System Configuration"
curl -s -X GET "$API_BASE/config" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 7: POST /dev/create-api-key (Development API Key Creation)
echo "7. POST /dev/create-api-key - Development API Key Creation"
curl -s -X POST "$API_BASE/dev/create-api-key" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "dev_user", "description": "Development test key"}' | python3 -m json.tool
echo

# Test 8: GET /metrics/current (Current Metrics)
echo "8. GET /metrics/current - Current Metrics"
curl -s -X GET "$API_BASE/metrics/current" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 9: GET /metrics/performance (Performance Metrics)
echo "9. GET /metrics/performance - Performance Metrics"
curl -s -X GET "$API_BASE/metrics/performance" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 10: GET /metrics/decompilation (Decompilation Metrics)
echo "10. GET /metrics/decompilation - Decompilation Metrics"
curl -s -X GET "$API_BASE/metrics/decompilation" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 11: GET /metrics/llm (LLM Metrics)
echo "11. GET /metrics/llm - LLM Metrics"
curl -s -X GET "$API_BASE/metrics/llm" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 12: GET /circuit-breakers (Circuit Breakers Status)
echo "12. GET /circuit-breakers - Circuit Breakers Status"
curl -s -X GET "$API_BASE/circuit-breakers" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 13: GET /circuit-breakers/{circuit_name} (Specific Circuit Breaker)
echo "13. GET /circuit-breakers/{circuit_name} - Specific Circuit Breaker"
curl -s -X GET "$API_BASE/circuit-breakers/openai_provider" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 14: POST /circuit-breakers/{circuit_name}/reset (Reset Circuit Breaker)
echo "14. POST /circuit-breakers/{circuit_name}/reset - Reset Circuit Breaker"
curl -s -X POST "$API_BASE/circuit-breakers/openai_provider/reset" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 15: POST /circuit-breakers/{circuit_name}/force-open (Force Open Circuit Breaker)
echo "15. POST /circuit-breakers/{circuit_name}/force-open - Force Open Circuit Breaker"
curl -s -X POST "$API_BASE/circuit-breakers/openai_provider/force-open" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 16: GET /circuit-breakers/health-check/all (All Circuit Breakers Health Check)
echo "16. GET /circuit-breakers/health-check/all - All Circuit Breakers Health Check"
curl -s -X GET "$API_BASE/circuit-breakers/health-check/all" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 17: GET /dashboards/overview (Dashboard Overview)
echo "17. GET /dashboards/overview - Dashboard Overview"
curl -s -X GET "$API_BASE/dashboards/overview" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 18: GET /dashboards/performance (Dashboard Performance)
echo "18. GET /dashboards/performance - Dashboard Performance"
curl -s -X GET "$API_BASE/dashboards/performance" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 19: GET /alerts (Alerts List)
echo "19. GET /alerts - Alerts List"
curl -s -X GET "$API_BASE/alerts" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 20: POST /alerts/check (Check Alerts)
echo "20. POST /alerts/check - Check Alerts"
curl -s -X POST "$API_BASE/alerts/check" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 21: POST /alerts/{alert_id}/acknowledge (Acknowledge Alert)
echo "21. POST /alerts/{alert_id}/acknowledge - Acknowledge Alert"
curl -s -X POST "$API_BASE/alerts/test_alert/acknowledge" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 22: POST /alerts/{alert_id}/resolve (Resolve Alert)
echo "22. POST /alerts/{alert_id}/resolve - Resolve Alert"
curl -s -X POST "$API_BASE/alerts/test_alert/resolve" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

# Test 23: GET /monitoring/prometheus (Prometheus Metrics)
echo "23. GET /monitoring/prometheus - Prometheus Metrics"
curl -s -X GET "$API_BASE/monitoring/prometheus" \
  -H "$AUTH_HEADER" | head -20
echo

# Test 24: GET /monitoring/health-summary (Health Summary)
echo "24. GET /monitoring/health-summary - Health Summary"
curl -s -X GET "$API_BASE/monitoring/health-summary" \
  -H "$AUTH_HEADER" | python3 -m json.tool
echo

echo "=== Admin Endpoints Testing Complete ==="