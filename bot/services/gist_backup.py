"""Bazani GitHub Gist orqali saqlash va tiklash (bepul, doimiy xotira).

Render.com va boshqa bepul xizmatlarda disk vaqtincha (restartda o'chadi).
Shu xizmat baza faylini har N daqiqada GitHub Gist'ga yuboradi va bot
ishga tushganda qayta yuklab oladi.

Faqat stdlib (urllib) ishlatiladi — Pydroid'da ham ishlaydi.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from bot import config

log = logging.getLogger(__name__)

API = "https://api.github.com"
FILE_NAME = "bot_data.b64"


def _request(method: str, url: str, payload: Optional[dict] = None, token: str = "") -> dict:
    """GitHub API chaqiruvi (bloklanmagan urllib bilan)."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "frilans-bot",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode() or "{}")


def is_enabled() -> bool:
    return bool(config.GIST_TOKEN)


# ---------------------------------------------------------------- tiklash
def _download_gist_to(db_path: str) -> bool:
    """Gist'dagi nusxani olib, baza fayliga yozadi. True = tiklandi."""
    token, gist_id = config.GIST_TOKEN, config.GIST_ID
    if not token or not gist_id:
        return False

    info = _request("GET", f"{API}/gists/{gist_id}", token=token)
    files = info.get("files", {})
    target = files.get(FILE_NAME)
    if not target or target.get("truncated"):
        log.warning("Gist'da to'liq baza topilmadi")
        return False

    content = target.get("content", "")
    data = base64.b64decode(content)
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Agar lokal fayl allaqachon kattaroq bo'lsa — tiklamaymiz
    if path.exists() and path.stat().st_size >= len(data):
        log.info("Lokal baza kattaroq — tiklash shart emas")
        return False

    path.write_bytes(data)
    log.info("✅ Baza GitHub Gist'dan tiklandi (%s bayt)", len(data))
    return True


async def restore_db(db_path: str) -> bool:
    """Ishga tushishdan oldin bazani tiklaydi."""
    if not is_enabled():
        return False
    try:
        return await asyncio.get_event_loop().run_in_executor(None, _download_gist_to, db_path)
    except Exception as exc:
        log.warning("Gist'dan tiklashda xatolik: %s", exc)
        return False


# ---------------------------------------------------------------- saqlash
def _upload_to_gist(db_path: str) -> str:
    """Lokal bazani gist'ga yozadi (yaratadi yoki yangilaydi). Gist ID qaytariladi."""
    token, gist_id = config.GIST_TOKEN, config.GIST_ID
    data = Path(db_path).read_bytes()
    encoded = base64.b64encode(data).decode()

    payload = {
        "description": "frilans-bot baza (avtomatik nusxa)",
        "public": False,
        "files": {FILE_NAME: {"content": encoded}},
    }

    if gist_id:
        info = _request("PATCH", f"{API}/gists/{gist_id}", payload=payload, token=token)
    else:
        info = _request("POST", f"{API}/gists", payload=payload, token=token)
        new_id = info.get("id", "")
        # Yangi Gist ID'ni .env fayliga yozib qo'yamiz (keyingi safar yangilaydi)
        _save_gist_id(new_id)
        log.info("🆕 Yangi Gist yaratildi: %s", new_id)

    return info.get("id", "")


def _save_gist_id(gist_id: str) -> None:
    if not gist_id:
        return
    config.GIST_ID = gist_id
    env_path = Path(config.PROJECT_DIR) / ".env"
    try:
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("GIST_ID="):
                lines[i] = f"GIST_ID={gist_id}"
                found = True
        if not found:
            lines.append(f"GIST_ID={gist_id}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        log.debug(".env ga GIST_ID yozilmadi: %s", exc)


async def save_db(db, db_path: str) -> bool:
    """Bazani gist'ga saqlaydi (WAL checkpoint bilan)."""
    if not is_enabled():
        return False
    try:
        # WAL faylini asosiy faylga birlashtirish
        try:
            await db._execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        await asyncio.get_event_loop().run_in_executor(None, _upload_to_gist, db_path)
        return True
    except Exception as exc:
        log.warning("Gist'ga saqlashda xatolik: %s", exc)
        return False


async def backup_worker(db, db_path: str, interval_minutes: int) -> None:
    """Fon vazifasi: bazani muntazam gist'ga nusxalaydi."""
    if not is_enabled():
        log.info("Gist nusxa o'chirilgan (GIST_TOKEN kiritilmagan)")
        return
    log.info("Gist nusxa ishga tushdi (har %s daqiqada)", interval_minutes)
    try:
        while True:
            await asyncio.sleep(max(1, interval_minutes) * 60)
            await save_db(db, db_path)
    except asyncio.CancelledError:
        # To'xtatishdan oldin oxirgi nusxa
        try:
            await save_db(db, db_path)
        except Exception:
            pass
        log.info("Gist nusxa to'xtatildi")
        raise
