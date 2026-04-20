#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/mobile"
BACKEND_DIR="$ROOT_DIR/backend"

echo "== Phase 4 QA Gate =="
echo "Root: $ROOT_DIR"

echo
echo "[1/4] Mobile typecheck"
(cd "$MOBILE_DIR" && npx tsc --noEmit)

echo
echo "[2/4] Mobile Expo doctor"
set +e
EXPO_DOCTOR_OUTPUT="$(cd "$MOBILE_DIR" && npx expo-doctor 2>&1)"
EXPO_DOCTOR_CODE=$?
set -e
echo "$EXPO_DOCTOR_OUTPUT"
if [[ $EXPO_DOCTOR_CODE -ne 0 ]]; then
  if [[ "$EXPO_DOCTOR_OUTPUT" == *"fetch failed"* ]] || [[ "$EXPO_DOCTOR_OUTPUT" == *"Connect Timeout Error"* ]]; then
    echo "WARN: expo-doctor falló por red externa (Expo API). Se continúa con el gate."
  else
    echo "ERROR: expo-doctor falló por motivo no transitorio."
    exit $EXPO_DOCTOR_CODE
  fi
fi

echo
echo "[3/4] Backend financial precision tests"
(cd "$BACKEND_DIR" && python -m pytest tests/test_math_engine.py -k "net_margin_precision_with_many_decimal_expenses or test_round_fiat_banker" -q)

echo
echo "[4/4] OCR stress smoke (20 concurrent)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:-}"
IMAGE_PATH="${IMAGE_PATH:-$ROOT_DIR/mobile/assets/icon.png}"

if ! curl -fsS "$BASE_URL/live" >/dev/null 2>&1; then
  echo "WARN: API no accesible en $BASE_URL (GET /live)."
  echo "      Se omite stress OCR. Levanta backend y reintenta:"
  echo "      BASE_URL=$BASE_URL IMAGE_PATH=$IMAGE_PATH TOKEN=<jwt> ./scripts/qa_gate_phase4.sh"
  exit 0
fi

(cd "$BACKEND_DIR" && python scripts/stress_api.py --base-url "$BASE_URL" --image "$IMAGE_PATH" --concurrency 20 ${TOKEN:+--token "$TOKEN"})

echo
echo "QA Gate Phase 4 OK"
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/mobile"
BACKEND_DIR="$ROOT_DIR/backend"

echo "== Phase 4 QA Gate =="
echo "Root: $ROOT_DIR"

echo
echo "[1/4] Mobile typecheck"
(cd "$MOBILE_DIR" && npx tsc --noEmit)

echo
echo "[2/4] Mobile Expo doctor"
(cd "$MOBILE_DIR" && npx expo-doctor)

echo
echo "[3/4] Backend financial precision tests"
(cd "$BACKEND_DIR" && python -m pytest tests/test_math_engine.py -k "net_margin_precision_with_many_decimal_expenses or test_round_fiat_banker" -q)

echo
echo "[4/4] OCR stress smoke (20 concurrent)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:-}"
IMAGE_PATH="${IMAGE_PATH:-$ROOT_DIR/mobile/assets/icon.png}"

if ! curl -fsS "$BASE_URL/live" >/dev/null 2>&1; then
  echo "WARN: API no accesible en $BASE_URL (GET /live)."
  echo "      Se omite stress OCR. Levanta backend y reintenta:"
  echo "      BASE_URL=$BASE_URL IMAGE_PATH=$IMAGE_PATH TOKEN=<jwt> ./scripts/qa_gate_phase4.sh"
  exit 0
fi

(cd "$BACKEND_DIR" && python scripts/stress_api.py --base-url "$BASE_URL" --image "$IMAGE_PATH" --concurrency 20 ${TOKEN:+--token "$TOKEN"})

echo
echo "QA Gate Phase 4 OK"
