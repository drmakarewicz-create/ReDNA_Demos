#!/bin/bash
# BeliefDNA Coach Integration Test
# Tests all endpoints and coach mode switching

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
USER_ID="TEST"

echo "🤔 BeliefDNA Coach Integration Test"
echo "===================================="
echo ""

# Test 1: Coach Mode Switch
echo "Test 1: Switching to BeliefDNA Coach..."
SWITCH_RESULT=$(curl -s -X POST "$API_BASE/users/$USER_ID/coach-mode" \
  -H "Content-Type: application/json" \
  -d '{"target_mode":"beliefdna_coach","context":{"source":"integration_test"}}')

if echo "$SWITCH_RESULT" | grep -q '"ok":true'; then
  echo "✅ Coach mode switch successful"
  echo "   Mode: $(echo "$SWITCH_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["new_mode"])')"
else
  echo "❌ Coach mode switch failed"
  echo "$SWITCH_RESULT"
  exit 1
fi
echo ""

# Test 2: Panel Endpoint
echo "Test 2: Testing /panel endpoint..."
PANEL_RESULT=$(curl -s "$API_BASE/api/coach/beliefdna_coach/panel?user_id=$USER_ID")

if echo "$PANEL_RESULT" | grep -q '"snapshot"'; then
  echo "✅ Panel endpoint working"
  echo "   Belief RR: $(echo "$PANEL_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["snapshot"]["belief_rr"])')"
  echo "   Templates: $(echo "$PANEL_RESULT" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["templates"]["cards"]))')"
else
  echo "❌ Panel endpoint failed"
  echo "$PANEL_RESULT"
  exit 1
fi
echo ""

# Test 3: Render Endpoint
echo "Test 3: Testing /render endpoint..."
RENDER_RESULT=$(curl -s -X POST "$API_BASE/api/coach/beliefdna_coach/render" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"'"$USER_ID"'","prompt":"Do humans have free will?","intent":"existential"}')

if echo "$RENDER_RESULT" | grep -q '"output"'; then
  echo "✅ Render endpoint working"
  OUTPUT=$(echo "$RENDER_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["output"])')
  echo "   Output: ${OUTPUT:0:80}..."
  echo "   Similarity: $(echo "$RENDER_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["similarity"]["overall"])')"
else
  echo "❌ Render endpoint failed"
  echo "$RENDER_RESULT"
  exit 1
fi
echo ""

# Test 4: Feedback Endpoint
echo "Test 4: Testing /feedback endpoint..."
FEEDBACK_RESULT=$(curl -s -X POST "$API_BASE/api/coach/beliefdna_coach/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"'"$USER_ID"'",
    "prompt":"Do humans have free will?",
    "output":"You would take a nuanced view",
    "user_rating":5,
    "notes":"Very accurate response"
  }')

if echo "$FEEDBACK_RESULT" | grep -q '"success":true'; then
  echo "✅ Feedback endpoint working"
  echo "   RR Delta: $(echo "$FEEDBACK_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["rr_delta"])')"
  echo "   Message: $(echo "$FEEDBACK_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["message"])')"
else
  echo "❌ Feedback endpoint failed"
  echo "$FEEDBACK_RESULT"
  exit 1
fi
echo ""

echo "===================================="
echo "✅ All BeliefDNA Coach tests passed!"
echo ""
echo "BeliefDNA Coach is ready to use at:"
echo "   http://localhost:3001/?persona=beliefdna_coach"
