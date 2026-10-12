import uuid
from datetime import datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Blacklist(db.Model):
    __tablename__ = "blacklist"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), nullable=False, unique=True, index=True)
    app_uuid = db.Column(db.Uuid, nullable=False, default=uuid.uuid4)
    blocked_reason = db.Column(db.String(255), nullable=True)
    # varchar(45) alcanza para IPv6 y funciona igual en PostgreSQL y SQLite (tests).
    request_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
