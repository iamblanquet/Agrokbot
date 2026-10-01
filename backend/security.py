"""Authentication primitives independent from the HTTP server and database."""
import hashlib
import hmac
import os


def pin_hash(pin):
    if not isinstance(pin, str):
        raise ValueError("PIN inválido")
    salt = os.urandom(16)
    key = hashlib.scrypt(pin.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + salt.hex() + "$" + key.hex()


def verify_pin(pin, encoded):
    try:
        if encoded.startswith("scrypt$"):
            _, salt_hex, key_hex = encoded.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(key_hex)
            actual = hashlib.scrypt(str(pin).encode(), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
            return hmac.compare_digest(actual, expected)
        return hmac.compare_digest(hashlib.sha256(("campo-pin:" + str(pin)).encode()).hexdigest(), encoded)
    except (ValueError, TypeError):
        return False


def pin_in_use(db, pin, excluding=None):
    return any(row["username"] != excluding and verify_pin(pin, row["pin_hash"]) for row in db.execute("SELECT username,pin_hash FROM app_users WHERE active=1"))
