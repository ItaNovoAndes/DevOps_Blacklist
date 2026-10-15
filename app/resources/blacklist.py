from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Blacklist
from ..schemas import blacklist_create_schema, blacklist_status_schema, normalize_email


class BlacklistCollection(Resource):
    @jwt_required()
    def post(self):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"msg": "El cuerpo de la petición debe ser un JSON"}, 400

        try:
            data = blacklist_create_schema.load(payload)
        except ValidationError as err:
            return {"msg": "Datos inválidos", "errors": err.messages}, 400

        if db.session.execute(
            db.select(Blacklist.id).filter_by(email=data["email"])
        ).first():
            return {"msg": "El email ya está en la lista negra"}, 409

        entry = Blacklist(
            email=data["email"],
            app_uuid=data["app_uuid"],
            blocked_reason=data["blocked_reason"],
            request_ip=request.remote_addr,
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except IntegrityError:
            # Otra instancia insertó el mismo email entre la consulta y el commit.
            db.session.rollback()
            return {"msg": "El email ya está en la lista negra"}, 409

        current_app.logger.info(
            "blacklist add email=%s ip=%s x_forwarded_for=%r",
            entry.email,
            entry.request_ip,
            request.headers.get("X-Forwarded-For"),
        )
        return {"msg": "Email agregado a la lista negra"}, 201


class BlacklistItem(Resource):
    @jwt_required()
    def get(self, email):
        email = normalize_email(email)
        entry = db.session.execute(
            db.select(Blacklist).filter_by(email=email)
        ).scalar_one_or_none()
        return blacklist_status_schema.dump(
            {
                "email": email,
                "is_blacklisted": entry is not None,
                "blocked_reason": entry.blocked_reason if entry else None,
            }
        ), 200
