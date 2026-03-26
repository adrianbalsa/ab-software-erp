#!/usr/bin/env bash
# AB Logistics OS — VPS setup (Ubuntu 24.04)
# Ejecutar como root: sudo ./infra/setup_server.sh
#
# Tareas:
# - Update apt + usuario no-root con sudo
# - Instalación Docker + Docker Compose plugin
# - UFW: solo 22/80/443 (salvo salida)
# - Fail2ban: protección SSH brute-force

set -euo pipefail

TARGET_USER="${TARGET_USER:-ablogistics}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: ejecuta como root (sudo)."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "[setup] Actualizando paquetes apt..."
apt-get update -y
apt-get upgrade -y

echo "[setup] Instalando dependencias básicas..."
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg lsb-release ufw fail2ban

echo "[setup] Creando usuario no-root: ${TARGET_USER}"
if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${TARGET_USER}"
fi

if ! getent group sudo >/dev/null; then
  apt-get install -y sudo
fi

usermod -aG sudo "${TARGET_USER}"

echo "[setup] Instalando Docker (oficial) + compose plugin..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
ARCH="$(dpkg --print-architecture)"

cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable
EOF

apt-get update -y
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

echo "[setup] Alineando permisos Docker para el usuario..."
usermod -aG docker "${TARGET_USER}"

echo "[setup] Configurando UFW..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "[setup] Preparando directorio Certbot (/var/www/certbot)..."
mkdir -p /var/www/certbot
chmod 0755 /var/www/certbot

echo "[setup] Configurando Fail2ban (sshd)..."
mkdir -p /etc/fail2ban/jail.d
cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
port = 22
protocol = tcp

# Ajusta según tus necesidades (y si usas VPN/GeoIP).
bantime = 1h
findtime = 10m
maxretry = 5
EOF

systemctl enable --now fail2ban

echo "[setup] OK."
echo "Usuario: ${TARGET_USER}"
echo "Puertos permitidos (UFW): 22, 80, 443"

