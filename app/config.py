import os


def _database_url():
    url = os.environ.get("DATABASE_URL", "")
    # Se acepta "postgres://" o "postgresql://" y se fuerza el driver psycopg2:
    # SQLAlchemy 2.1 usa psycopg (v3) por defecto, que no está en requirements.txt.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Config:
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    # Token estático: sin expiración (acuerdo del equipo).
    JWT_ACCESS_TOKEN_EXPIRES = False

    # Necesario para que Flask-RESTful deje pasar los errores de Flask-JWT-Extended
    # a sus manejadores (si no, responde 500 en vez de 401).
    PROPAGATE_EXCEPTIONS = True

    # Número de proxies de confianza delante de gunicorn.
    # En Beanstalk: balanceador (ALB) + nginx = 2.
    PROXY_FIX_X_FOR = int(os.environ.get("PROXY_FIX_X_FOR", "2"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    JWT_SECRET_KEY = "test-secret-key-with-at-least-32-bytes"
