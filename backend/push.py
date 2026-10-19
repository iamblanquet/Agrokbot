"""Web Push keys live in the persistent volume, never in the repository."""
import base64
import json
import os
from urllib.parse import urlsplit


def validate_subscription(value):
    if not isinstance(value, dict):
        raise ValueError('Suscripción inválida')
    endpoint = value.get('endpoint', '')
    url = urlsplit(endpoint)
    host = url.hostname or ''
    allowed = host == 'fcm.googleapis.com' or host.endswith('.push.services.mozilla.com') or host == 'updates.push.services.mozilla.com' or host.endswith('.notify.windows.com') or host == 'web.push.apple.com'
    if not allowed or url.scheme != 'https' or url.port not in (None, 443) or url.username or url.password or len(endpoint) > 2048:
        raise ValueError('Proveedor de notificaciones no admitido')
    keys = value.get('keys', {})
    for key, size in [('p256dh', 65), ('auth', 16)]:
        raw = keys.get(key, '')
        try:
            decoded = base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4))
            if len(decoded) != size:
                raise ValueError()
        except Exception:
            raise ValueError('Clave de suscripción inválida') from None
    return {'endpoint': endpoint, 'keys': {k: keys[k] for k in ('p256dh', 'auth')}}


class Push:
    def __init__(self, folder, public_url):
        self.path = folder / 'push-vapid.pem'
        self.public_url = public_url

    def public_key(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        if not self.path.exists():
            key = ec.generate_private_key(ec.SECP256R1())
            data = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            try:
                with open(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as stream:
                    stream.write(data)
            except FileExistsError:
                pass
        key = serialization.load_pem_private_key(self.path.read_bytes(), password=None)
        raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(raw).decode().rstrip('=')

    def send(self, subscription, data):
        from pywebpush import webpush
        validate_subscription(subscription)
        webpush(subscription, json.dumps(data), vapid_private_key=str(self.path),
                vapid_claims={'sub': self.public_url}, ttl=10800, timeout=20)
