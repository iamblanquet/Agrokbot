"""Small JSON HTTP client shared by ERP and Telegram integrations."""
import json
import urllib.error
import urllib.request


class RemoteFailure(Exception):
    def __init__(self, message, ambiguous=False):
        self.message, self.ambiguous = message, ambiguous


def request_json(url, payload=None, headers=None, timeout=15):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        message = f"El servicio externo respondió HTTP {error.code}."
        try:
            parsed = json.loads(error.read().decode("utf-8", errors="ignore"))
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), str) and len(parsed["error"]) < 300:
                message = f"ERP: {parsed['error']}"
        except Exception:
            pass
        raise RemoteFailure(message, error.code >= 500) from None
    except (OSError, ValueError):
        raise RemoteFailure("No se pudo confirmar la respuesta del servicio externo.", True) from None
