# Usamos una versión ligera de Python para minimizar costes
FROM python:3.11-slim

# Creamos el directorio de trabajo
WORKDIR /app

# Copiamos e instalamos las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código de tu ERP
COPY . .

# Railway asigna un puerto dinámico, lo preparamos
ENV PORT=8080
EXPOSE $PORT

# Comando maestro para arrancar Streamlit
CMD streamlit run main.py --server.port=$PORT --server.address=0.0.0.0
