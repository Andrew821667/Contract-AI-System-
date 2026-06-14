# -*- coding: utf-8 -*-
"""Админ-эндпоинты управления регулярным обновлением БЗ (#4):
  GET  /update/status  — статус последнего/текущего прогона (kb_update_status.json)
  POST /update/run     — ручной запуск обновления в фоне
  GET  /update/config  — К+ логин (пароль маскирован), расписание cron, telegram
  PUT  /update/config  — изменить К+ логин/пароль (запись в ~/.config/consultant/.env)
Только для role=admin (require_admin). Регистрируется импортом в __init__.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import require_admin
from src.models.auth_models import User
from .routes import router  # тот же APIRouter (единый префикс /rag)

_HOME = Path.home()
STATUS_FILE = _HOME / "consultant-data" / "kb_update_status.json"
ENV_FILE = _HOME / ".config" / "consultant" / ".env"
UPDATE_SH = Path("/Users/legalai/projects/Contract-AI-System-/scripts/kb_update.sh")


@router.get("/update/status")
async def kb_update_status(current_user: User = Depends(require_admin)):
    """Статус последнего/текущего прогона обновления БЗ."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"state": "unknown", "message": "статус ещё не сформирован"}


@router.post("/update/run")
async def kb_update_run(current_user: User = Depends(require_admin)):
    """Ручной запуск обновления БЗ в фоне (тот же скрипт, что по cron)."""
    if not UPDATE_SH.exists():
        raise HTTPException(status_code=404, detail="скрипт kb_update.sh не найден")
    subprocess.Popen(
        ["/bin/sh", str(UPDATE_SH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    return {"started": True, "message": "обновление БЗ запущено в фоне"}


def _read_env() -> dict:
    d = {}
    if ENV_FILE.exists():
        for ln in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    return d


@router.get("/update/config")
async def kb_update_config(current_user: User = Depends(require_admin)):
    """Текущие изменяемые данные: К+ логин, факт наличия пароля, расписание, telegram."""
    env = _read_env()
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        cron = ""
    schedule = [l for l in cron.splitlines() if "kb_update" in l and not l.strip().startswith("#")]
    return {
        "consultant_login": env.get("CONSULTANT_USERNAME", ""),
        "consultant_password_set": bool(env.get("CONSULTANT_PASSWORD")),
        "schedule": schedule,
        "telegram_configured": bool(env.get("TELEGRAM_BOT_TOKEN")),
    }


class KBConfigUpdate(BaseModel):
    consultant_login: Optional[str] = None
    consultant_password: Optional[str] = None


@router.put("/update/config")
async def kb_update_config_save(body: KBConfigUpdate, current_user: User = Depends(require_admin)):
    """Изменить К+ логин/пароль (записывается в ~/.config/consultant/.env, chmod 600)."""
    env = _read_env()
    if body.consultant_login is not None:
        env["CONSULTANT_USERNAME"] = body.consultant_login
    if body.consultant_password:
        env["CONSULTANT_PASSWORD"] = body.consultant_password
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_FILE, 0o600)
    except Exception:
        pass
    return {"saved": True, "message": "данные К+ обновлены"}
