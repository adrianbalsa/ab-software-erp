#!/bin/bash
# smoke_test.sh - Ejecutar tras: docker compose -f docker-compose.prod.yml up -d

echo "🔍 Iniciando Smoke Test del Búnker..."

# 1. Verificar Backend (Ready endpoint)
status_be=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ready)
if [ "$status_be" == "200" ]; then echo "✅ Backend: ONLINE"; else echo "❌ Backend: OFFLINE ($status_be)"; fi

# 2. Verificar Frontend
status_fe=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/)
if [ "$status_fe" == "200" ]; then echo "✅ Frontend: ONLINE"; else echo "❌ Frontend: OFFLINE ($status_fe)"; fi

# 3. Verificar VeriFactu (Fiscal Health)
status_vf=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/verifactu)
if [ "$status_vf" == "200" ]; then echo "✅ VeriFactu Logic: CERTIFIED"; else echo "⚠️ VeriFactu: CHECK LOGS"; fi

echo "🏁 Test completado."
