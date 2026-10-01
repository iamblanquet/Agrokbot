"""Telegram Bot API transport used by the outbox and the bot workflow."""
import json
import secrets
import urllib.error
import urllib.request

from backend.http_client import RemoteFailure


def safe_caption(text, limit=1024):
    if not text:
        return ""
    if len(text.encode("utf-16-le")) // 2 <= limit:
        return text
    encoded = text.encode("utf-16-le")
    trimmed = encoded[:(limit - 3) * 2].decode("utf-16-le", errors="ignore")
    return trimmed + "..."


class TelegramClient:
    def __init__(self, remote, settings):
        self.remote = remote
        self.settings = settings

    def request(self, method, payload):
        settings = self.settings()
        if not settings["token"] or not settings["chat_id"]:
            raise RemoteFailure("Faltan el token del bot o el identificador del supergrupo.")
        result = self.remote(f"https://api.telegram.org/bot{settings['token']}/{method}", payload)
        if not result.get("ok"):
            raise RemoteFailure("Telegram rechazó la operación. Revisa permisos y configuración.")
        return result["result"]

    def photo(self, photo, thread_id, message_id=None, caption="", reply_markup=None):
        settings = self.settings()
        if not settings["token"] or not settings["chat_id"]:
            raise RemoteFailure("Falta configurar Telegram.")
        boundary = "Campo" + secrets.token_hex(16)
        fields = {"chat_id": settings["chat_id"], "message_thread_id": str(thread_id)}
        if caption:
            fields["caption"] = safe_caption(caption)
        if message_id:
            fields["reply_parameters"] = json.dumps({"message_id": int(message_id)})
        if reply_markup:
            fields["reply_markup"] = json.dumps(reply_markup)
        chunks = []
        for key, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="evidencia.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode(), photo["data"], f"\r\n--{boundary}--\r\n".encode()])
        request = urllib.request.Request(f"https://api.telegram.org/bot{settings['token']}/sendPhoto", data=b"".join(chunks), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.load(response)
            if not result.get("ok"):
                raise RemoteFailure("Telegram rechazó la fotografía.")
            return str(result["result"]["message_id"])
        except urllib.error.HTTPError as error:
            raise RemoteFailure(f"Telegram respondió HTTP {error.code} al enviar la fotografía.", error.code >= 500) from None
        except (OSError, ValueError, KeyError, TypeError):
            raise RemoteFailure("No se pudo confirmar el envío de la fotografía. Verifica en Telegram antes de repetir.", True) from None

    def media_group(self, photos, thread_id, caption=""):
        settings = self.settings()
        if not settings["token"] or not settings["chat_id"]:
            raise RemoteFailure("Falta configurar Telegram.")
        boundary = "Campo" + secrets.token_hex(16)
        media_items = []
        for index in range(len(photos)):
            item = {"type": "photo", "media": f"attach://file_{index}"}
            if index == 0 and caption:
                item["caption"] = safe_caption(caption)
            media_items.append(item)
        fields = {"chat_id": settings["chat_id"], "message_thread_id": str(thread_id), "media": json.dumps(media_items)}
        chunks = []
        for key, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        for index, photo in enumerate(photos):
            chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file_{index}"; filename="foto_{index}.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode(), photo["data"], b"\r\n"])
        chunks.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(f"https://api.telegram.org/bot{settings['token']}/sendMediaGroup", data=b"".join(chunks), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            if not result.get("ok"):
                raise RemoteFailure("Telegram rechazó el grupo de fotografías.")
            return [str(message["message_id"]) for message in result["result"]]
        except urllib.error.HTTPError as error:
            raise RemoteFailure(f"Telegram respondió HTTP {error.code} al enviar las fotografías.", error.code >= 500) from None
        except (OSError, ValueError, KeyError, TypeError):
            raise RemoteFailure("No se pudo confirmar el envío del grupo de fotografías.", True) from None
