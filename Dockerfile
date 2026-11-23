# Imagen del microservicio blacklist-ms.
# Base desde ECR Public (espejo de Docker Hub) para evitar el límite de descargas en CodeBuild.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias (solo producción) para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo el código necesario para ejecutar la app.
COPY app/ ./app/
COPY application.py VERSION ./

# Usuario sin privilegios.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Configuración no sensible del agente de New Relic (APM).
# NEW_RELIC_LICENSE_KEY NO va en la imagen: en Fargate se inyecta desde
# Parameter Store (/blacklist-ms/NEW_RELIC_LICENSE_KEY) y en local con `docker run -e`.
ENV NEW_RELIC_APP_NAME="blacklist-ms" \
    NEW_RELIC_LOG=stdout \
    NEW_RELIC_LOG_LEVEL=info \
    NEW_RELIC_DISTRIBUTED_TRACING_ENABLED=true

# DATABASE_URL, JWT_SECRET_KEY y NEW_RELIC_LICENSE_KEY NO van en la imagen: se pasan al ejecutar el contenedor.
EXPOSE 5000

# newrelic-admin envuelve a gunicorn para instrumentar Flask y psycopg2 automáticamente.
ENTRYPOINT ["newrelic-admin", "run-program"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "application:application"]
