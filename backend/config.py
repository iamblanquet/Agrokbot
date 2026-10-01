"""Carga centralizada de configuración de entorno para el servidor."""
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    erp_mode: str
    telegram_mode: str
    erp_url: str
    erp_key: str
    bot_token: str
    chat_id: str
    user: str
    responsible_name: str
    responsible_map: str
    password: str
    public_url: str
    allowed_users: set


def load_config(root, environ: Mapping[str, str]):
    return AppConfig(
        data_dir=Path(environ.get("DATA_DIR", str(root / "data"))),
        erp_mode=environ.get("ERP_MODE", "demo"),
        telegram_mode=environ.get("TELEGRAM_MODE", "demo"),
        erp_url=environ.get("ERP_API_URL", "").rstrip("/"),
        erp_key=environ.get("ERP_API_KEY", ""),
        bot_token=environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=environ.get("TELEGRAM_CHAT_ID", ""),
        user=environ.get("APP_USER", "dev"),
        responsible_name=environ.get("APP_RESPONSIBLE_NAME", "").strip(),
        responsible_map=environ.get("USER_RESPONSIBLE_MAP", "").strip(),
        password=environ.get("APP_PASSWORD", "campo-demo-2026"),
        public_url=environ.get("PUBLIC_URL", "").rstrip("/"),
        allowed_users=set(filter(None, environ.get("TELEGRAM_ALLOWED_USERS", "").split(","))),
    )
