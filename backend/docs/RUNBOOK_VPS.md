📘 Runbook de Producción: AB Logistics OS
Requisitos Previos:

Un VPS "limpio" con Ubuntu 24.04 LTS recién instalado.

Acceso SSH como root.

Acceso al panel de DNS de tu dominio.

Fase 0: Propagación DNS (Desde tu panel de dominio)
Antes de tocar el servidor, necesitamos que internet sepa dónde está.

Ve a tu proveedor de dominios (Cloudflare, DonDominio, etc.).

Crea un Registro A para api.tu-dominio.com apuntando a la IP pública de tu VPS.

Crea un Registro A para app.tu-dominio.com apuntando a la misma IP pública.

Nota: Espera unos minutos y verifica con ping app.tu-dominio.com en tu terminal local que ya responde la IP correcta.

Fase 1: Hardening e Inicialización (En el VPS)
Conéctate al servidor por primera vez:

Bash
ssh root@<IP_DEL_VPS>
Sube y ejecuta el script de configuración que creamos:

Bash
# Copia el código de tu repositorio o clónalo
git clone <URL_DE_TU_REPO> ab_logistics
cd ab_logistics

# Dale permisos y ejecuta
chmod +x infra/setup_server.sh
./infra/setup_server.sh
El script creará el usuario ablogistics, instalará Docker, UFW (Firewall) y Fail2ban.
Cierra la sesión de root y vuelve a entrar con tu nuevo usuario seguro:

Bash
exit
ssh ablogistics@<IP_DEL_VPS>
cd ab_logistics
Fase 2: Inyección de Secretos (Variables de Entorno)
El código está ahí, pero le falta el "combustible".

Crea el archivo de entorno de producción:

Bash
nano .env.prod
Pega todas tus variables reales (SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, NEXT_PUBLIC_GOOGLE_MAPS_API_KEY, etc.). Guarda y cierra (Ctrl+O, Enter, Ctrl+X).

Fase 3: Certificados SSL y Proxy (Nginx)
Vamos a poner el "candado verde" antes de levantar la aplicación.

Instala Nginx y Certbot:

Bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
Copia tu configuración de Nginx al directorio de sitios disponibles:

Bash
sudo cp infra/nginx.conf /etc/nginx/sites-available/ablogistics
sudo ln -s /etc/nginx/sites-available/ablogistics /etc/nginx/sites-enabled/
# Elimina el default para que no haya conflictos
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t  # Verifica que la sintaxis es correcta
sudo systemctl reload nginx
Genera los certificados SSL mágicamente:

Bash
sudo certbot --nginx -d api.tu-dominio.com -d app.tu-dominio.com
Certbot modificará automáticamente tu nginx.conf para añadir las rutas de los certificados.

Fase 4: Ignición (Levantar Contenedores)
El servidor está blindado y el tráfico HTTPS está enrutado. Es hora de arrancar el motor.

Bash
# Crea el directorio para la persistencia de Redis
mkdir -p data/redis

# Construye y levanta en segundo plano
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
Fase 5: Verificación de Salud (Healthchecks)
Comprueba que los tres cilindros del motor (Backend, Frontend, Redis) están girando:

Bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=50 -f
Abre tu navegador en el móvil o en el PC y entra a https://app.tu-dominio.com. Si ves el login con el diseño Dark Enterprise, el despliegue ha sido un éxito rotundo.