import socket
import urllib.request
from pathlib import Path

from flask_restful import Resource

VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"
IMDS_URL = "http://169.254.169.254/latest"

_instance_id = None


def read_version():
    try:
        return VERSION_FILE.read_text().strip()
    except OSError:
        return "unknown"


def fetch_instance_id(timeout=1):
    """Obtiene el instance-id de EC2 con IMDSv2; si falla, usa el hostname."""
    try:
        token_req = urllib.request.Request(
            f"{IMDS_URL}/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        )
        with urllib.request.urlopen(token_req, timeout=timeout) as resp:
            token = resp.read().decode()
        id_req = urllib.request.Request(
            f"{IMDS_URL}/meta-data/instance-id",
            headers={"X-aws-ec2-metadata-token": token},
        )
        with urllib.request.urlopen(id_req, timeout=timeout) as resp:
            return resp.read().decode()
    except OSError:
        return socket.gethostname()


def get_instance_id():
    global _instance_id
    if _instance_id is None:
        _instance_id = fetch_instance_id()
    return _instance_id


VERSION = read_version()


class Ping(Resource):
    def get(self):
        return {"status": "ok", "version": VERSION, "instance_id": get_instance_id()}, 200
