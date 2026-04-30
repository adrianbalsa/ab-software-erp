#!/usr/bin/env bash
# Evidencia reproducible TLS (DD §3.1) — no sustituye informe SSL Labs; complementa cadena y protocolos.
# Uso: ./scripts/collect_tls_evidence.sh api.ejemplo.com
set -euo pipefail

HOST="${1:-}"
if [[ -z "${HOST}" ]]; then
  echo "Uso: $0 <hostname>   # ej. api.tudominio.com" >&2
  exit 1
fi
# Placeholder de docs: sustituir por el FQDN real de prod (API o app).
if [[ "${HOST}" == "TU_HOST" || "${HOST}" == "tu_host" ]]; then
  echo "Error: \"${HOST}\" es un ejemplo en la documentación. Pasa tu dominio real, p. ej. api.midominio.com" >&2
  exit 2
fi

echo "## TLS — captura local ($(date -u +"%Y-%m-%dT%H:%M:%SZ") UTC)"
echo ""
echo "**Host:** \`${HOST}\`"
echo ""
echo "### Cadena (subject / emisor / validez)"
echo '```'
echo | openssl s_client -servername "${HOST}" -connect "${HOST}:443" -tls1_2 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates 2>/dev/null || echo "(fallo openssl: comprobar red/DNS/firewall)"
echo '```'
echo ""
echo "### Negociación sugerida (curl)"
echo '```'
curl -fsSI --max-time 15 "https://${HOST}/health" 2>&1 | head -n 20 || true
echo '```'
echo ""
echo "### SSL Labs (evidencia externa con nota)"
echo "1. Abrir https://www.ssllabs.com/ssltest/analyze.html?d=${HOST}&latest"
echo "2. Esperar a que finalice el análisis (puede tardar varios minutos)."
echo "3. Objetivo: **rating A o superior** en producción; documentar cualquier advertencia (cadena incompleta, TLS antiguo)."
echo "4. Archivar: PDF o captura + URL del resultado en el expediente del comité."
echo ""
