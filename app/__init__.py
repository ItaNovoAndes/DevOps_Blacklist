import logging

import click
from flask import Flask
from flask_jwt_extended import create_access_token
from flask_restful import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, jwt, ma
from .resources.blacklist import BlacklistCollection, BlacklistItem
from .resources.health import Ping


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    missing = [k for k in ("SQLALCHEMY_DATABASE_URI", "JWT_SECRET_KEY") if not app.config.get(k)]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno: DATABASE_URL y/o JWT_SECRET_KEY "
            f"(sin valor: {', '.join(missing)})"
        )

    # Toma la IP real del cliente contando solo los proxies de confianza
    # (no el primer valor de X-Forwarded-For, que el cliente puede falsificar).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_FIX_X_FOR"])

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)
        app.logger.setLevel(logging.INFO)

    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)
    register_jwt_handlers()

    api = Api(app)
    api.add_resource(BlacklistCollection, "/blacklists")
    api.add_resource(BlacklistItem, "/blacklists/<string:email>")
    api.add_resource(Ping, "/ping")

    register_commands(app)
    return app


def register_jwt_handlers():
    # Flask-JWT-Extended responde 422 ante un token mal formado; el contrato pide 401.
    @jwt.unauthorized_loader
    def missing_token(reason):
        return {"msg": f"Token de autorización requerido: {reason}"}, 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return {"msg": f"Token inválido: {reason}"}, 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return {"msg": "Token expirado"}, 401


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas en la base de datos (ejecutar una sola vez)."""
        db.create_all()
        click.echo("Tablas creadas (o ya existían).")

    @app.cli.command("generate-token")
    @click.option("--identity", default="blacklist-ms-client", show_default=True)
    def generate_token(identity):
        """Genera el Bearer token estático (sin expiración) firmado con JWT_SECRET_KEY."""
        click.echo(create_access_token(identity=identity, expires_delta=False))
