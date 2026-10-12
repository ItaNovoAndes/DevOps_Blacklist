from marshmallow import EXCLUDE, fields, pre_load, validate

from .extensions import ma


def normalize_email(value):
    return value.strip().lower() if isinstance(value, str) else value


class BlacklistCreateSchema(ma.Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True, validate=validate.Length(max=320))
    app_uuid = fields.UUID(required=True)
    blocked_reason = fields.String(
        load_default=None, allow_none=True, validate=validate.Length(max=255)
    )

    @pre_load
    def normalize(self, data, **kwargs):
        if isinstance(data, dict) and "email" in data:
            data = {**data, "email": normalize_email(data["email"])}
        return data


class BlacklistStatusSchema(ma.Schema):
    email = fields.String()
    is_blacklisted = fields.Boolean()
    blocked_reason = fields.String(allow_none=True)


blacklist_create_schema = BlacklistCreateSchema()
blacklist_status_schema = BlacklistStatusSchema()
