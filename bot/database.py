"""Baza qatlami: barcha SQL funksiyalari shu faylda (aiosqlite).

Keyinchalik PostgreSQL'ga o'tish uchun faqat shu fayldagi SQL'ni almashtirish kifoya —
handlerlar baza qatlamiga faqat shu modul orqali muroqat qiladi.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import aiosqlite

from bot.config import DB_PATH, TZ_OFFSET_HOURS


# ---------------------------------------------------------------- vaqt yordamchilari
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat(timespec="seconds")


def today_start_iso() -> str:
    """Bugungi kunning boshi (mahalliy vaqt bo'yicha, UTC da qaytariladi)."""
    local = now_utc() + timedelta(hours=TZ_OFFSET_HOURS)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return (start_local - timedelta(hours=TZ_OFFSET_HOURS)).isoformat(timespec="seconds")


def minutes_ago_iso(minutes: int) -> str:
    return (now_utc() - timedelta(minutes=minutes)).isoformat(timespec="seconds")


# ---------------------------------------------------------------- sxema
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    username     TEXT,
    full_name    TEXT,
    role         TEXT DEFAULT NULL,
    rating_sum   REAL    DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    is_active    INTEGER DEFAULT 1,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    UNIQUE(category_id, name)
);

CREATE TABLE IF NOT EXISTS executor_skills (
    user_id  INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id       INTEGER NOT NULL,
    skill_id          INTEGER,
    skill_name        TEXT,
    description       TEXT,
    budget            TEXT,
    deadline          TEXT,
    status            TEXT    NOT NULL DEFAULT 'open',
    executor_id       INTEGER,
    is_custom         INTEGER DEFAULT 0,
    timeout_notified  INTEGER DEFAULT 0,
    customer_chat_id  INTEGER,
    customer_message_id INTEGER,
    created_at        TEXT    NOT NULL,
    taken_at          TEXT
);

CREATE TABLE IF NOT EXISTS order_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL,
    executor_id INTEGER NOT NULL,
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE,
    executor_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    score       INTEGER NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS complaints (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER,
    user_id    INTEGER,
    text       TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_es_skill ON executor_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_es_user  ON executor_skills(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_executor ON orders(executor_id);
CREATE INDEX IF NOT EXISTS idx_skills_cat ON skills(category_id);
"""


class Database:
    """SQLite bilan ishlash. Bitta ulanish (connection) + qo'shimcha lock."""

    def __init__(self, path: str = "bot_data.db") -> None:
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock: Optional[asyncio.Lock] = None

    # ---------------------------------------------------------- ulanish
    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.path)
            self._conn.row_factory = aiosqlite.Row
            self._lock = asyncio.Lock()
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            finally:
                self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Baza hali ulanmagan! `await db.connect()` ni chaqiring.")
        return self._conn

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ---------------------------------------------------------- pastki darajali SQL
    async def _execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        async with self.lock:
            cur = await self.conn.execute(sql, tuple(params))
            await self.conn.commit()
            rowcount = cur.rowcount
            await cur.close()
            return rowcount

    async def _fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
        async with self.lock:
            cur = await self.conn.execute(sql, tuple(params))
            row = await cur.fetchone()
            await cur.close()
            return dict(row) if row else None

    async def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        async with self.lock:
            cur = await self.conn.execute(sql, tuple(params))
            rows = await cur.fetchall()
            await cur.close()
            return [dict(r) for r in rows]

    # ---------------------------------------------------------- sxema / seed
    async def init_schema(self) -> None:
        await self.connect()
        async with self.lock:
            await self.conn.executescript(SCHEMA)
            await self.conn.commit()

    async def seed_categories(self, categories: dict[str, list[str]]) -> None:
        """Boshlang'ich katalogni bazaga yozadi (mavjudlari o'zgartirmaydi)."""
        for cat_name, skill_names in categories.items():
            cat_id = await self.get_or_create_category(cat_name)
            for skill_name in skill_names:
                await self.get_or_create_skill(cat_id, skill_name)

    async def get_or_create_category(self, name: str) -> int:
        name = name.strip()
        row = await self._fetchone("SELECT id FROM categories WHERE name = ?", (name,))
        if row:
            return int(row["id"])
        await self._execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        row = await self._fetchone("SELECT id FROM categories WHERE name = ?", (name,))
        return int(row["id"])

    async def get_or_create_skill(self, category_id: int, name: str) -> int:
        name = name.strip()
        row = await self._fetchone(
            "SELECT id FROM skills WHERE category_id = ? AND name = ?", (category_id, name)
        )
        if row:
            return int(row["id"])
        await self._execute(
            "INSERT OR IGNORE INTO skills (category_id, name) VALUES (?, ?)", (category_id, name)
        )
        row = await self._fetchone(
            "SELECT id FROM skills WHERE category_id = ? AND name = ?", (category_id, name)
        )
        return int(row["id"])

    # ---------------------------------------------------------- foydalanuvchilar
    async def get_or_create_user(
        self, user_id: int, username: Optional[str], full_name: str
    ) -> dict:
        row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if row is None:
            await self._execute(
                "INSERT INTO users (user_id, username, full_name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, full_name, now_iso()),
            )
            row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return row  # type: ignore[return-value]

        new_username = username if username is not None else row["username"]
        new_name = full_name or row["full_name"]
        if new_username != row["username"] or new_name != row["full_name"]:
            await self._execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (new_username, new_name, user_id),
            )
            row["username"] = new_username
            row["full_name"] = new_name
        return row

    async def get_user(self, user_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

    async def set_role(self, user_id: int, role: str) -> None:
        await self._execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))

    async def deactivate_user(self, user_id: int) -> None:
        await self._execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))

    async def activate_user(self, user_id: int) -> None:
        await self._execute("UPDATE users SET is_active = 1 WHERE user_id = ?", (user_id,))

    async def count_users(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM users")
        return int(row["c"]) if row else 0

    async def count_users_by_role(self, role: str) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM users WHERE role = ?", (role,))
        return int(row["c"]) if row else 0

    async def get_all_user_ids(self) -> list[int]:
        rows = await self._fetchall("SELECT user_id FROM users WHERE is_active = 1 ORDER BY user_id")
        return [int(r["user_id"]) for r in rows]

    # ---------------------------------------------------------- sohalar / yo'nalishlar
    async def get_categories(self) -> list[dict]:
        return await self._fetchall("SELECT * FROM categories ORDER BY id")

    async def get_categories_with_skills(self) -> list[dict]:
        rows = await self._fetchall(
            """
            SELECT c.id, c.name,
                   (SELECT COUNT(*) FROM skills s WHERE s.category_id = c.id) AS skill_count
            FROM categories c
            ORDER BY c.id
            """
        )
        return [r for r in rows if int(r["skill_count"]) > 0]

    async def get_category(self, category_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM categories WHERE id = ?", (category_id,))

    async def get_category_by_name(self, name: str) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM categories WHERE name = ?", (name.strip(),))

    async def get_skills(self, category_id: int) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM skills WHERE category_id = ? ORDER BY id", (category_id,)
        )

    async def get_skill(self, skill_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM skills WHERE id = ?", (skill_id,))

    async def get_skills_all(self) -> list[dict]:
        return await self._fetchall("SELECT * FROM skills ORDER BY id")

    async def count_skills(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM skills")
        return int(row["c"]) if row else 0

    async def get_skill_with_category(self, skill_id: int) -> Optional[dict]:
        return await self._fetchone(
            """
            SELECT s.id AS skill_id, s.name AS skill_name,
                   c.id AS category_id, c.name AS category_name
            FROM skills s JOIN categories c ON c.id = s.category_id
            WHERE s.id = ?
            """,
            (skill_id,),
        )

    # ---------------------------------------------------------- ijrochi yo'nalishlari
    async def get_executor_skill_ids(self, user_id: int) -> list[int]:
        rows = await self._fetchall(
            "SELECT skill_id FROM executor_skills WHERE user_id = ? ORDER BY skill_id", (user_id,)
        )
        return [int(r["skill_id"]) for r in rows]

    async def get_executor_skills(self, user_id: int) -> list[dict]:
        return await self._fetchall(
            """
            SELECT s.id AS id, s.name AS skill_name, c.name AS category_name
            FROM executor_skills es
            JOIN skills s   ON s.id = es.skill_id
            JOIN categories c ON c.id = s.category_id
            WHERE es.user_id = ?
            ORDER BY c.id, s.id
            """,
            (user_id,),
        )

    async def set_executor_skills(self, user_id: int, skill_ids: Iterable[int]) -> None:
        ids = [int(i) for i in skill_ids]
        async with self.lock:
            await self.conn.execute("DELETE FROM executor_skills WHERE user_id = ?", (user_id,))
            if ids:
                await self.conn.executemany(
                    "INSERT OR IGNORE INTO executor_skills (user_id, skill_id) VALUES (?, ?)",
                    [(user_id, sid) for sid in ids],
                )
            await self.conn.commit()

    async def executor_has_skill(self, user_id: int, skill_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 AS x FROM executor_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, skill_id),
        )
        return row is not None

    async def find_executors_for_skill(self, skill_id: int, exclude_user_id: int) -> list[dict]:
        """Bu yo'nalishni tanlagan faol ijrochilar (buyurtmachidan tashqari)."""
        return await self._fetchall(
            """
            SELECT u.user_id, u.username, u.full_name
            FROM users u
            JOIN executor_skills es ON es.user_id = u.user_id
            WHERE es.skill_id = ? AND u.user_id != ? AND u.is_active = 1
            ORDER BY u.user_id
            """,
            (skill_id, exclude_user_id),
        )

    async def find_all_executors(self, exclude_user_id: int) -> list[dict]:
        """Barcha faol ijrochilar (maxsus/ro'yxatda yo'q yo'nalishlar uchun)."""
        return await self._fetchall(
            """
            SELECT user_id, username, full_name FROM users
            WHERE role = 'executor' AND is_active = 1 AND user_id != ?
            ORDER BY user_id
            """,
            (exclude_user_id,),
        )

    # ---------------------------------------------------------- buyurtmalar
    async def create_order(
        self,
        customer_id: int,
        skill_id: Optional[int],
        skill_name: str,
        description: str,
        budget: str,
        deadline: str,
        is_custom: bool = False,
    ) -> int:
        async with self.lock:
            cur = await self.conn.execute(
                """
                INSERT INTO orders (customer_id, skill_id, skill_name, description, budget,
                                    deadline, status, is_custom, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    customer_id,
                    skill_id,
                    skill_name,
                    description,
                    budget,
                    deadline,
                    1 if is_custom else 0,
                    now_iso(),
                ),
            )
            await self.conn.commit()
            order_id = int(cur.lastrowid)
            await cur.close()
            return order_id

    async def get_order(self, order_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))

    async def set_order_customer_message(self, order_id: int, chat_id: int, message_id: int) -> None:
        await self._execute(
            "UPDATE orders SET customer_chat_id = ?, customer_message_id = ? WHERE id = ?",
            (chat_id, message_id, order_id),
        )

    async def take_order(self, order_id: int, executor_id: int) -> bool:
        """Atomik qabul qilish: faqat `status='open'` bo'lsa o'tadi.

        True  -> buyurtma shu ijrochiga berildi
        False -> kech qoldi (boshqa ijrochi oldi)
        """
        async with self.lock:
            cur = await self.conn.execute(
                "UPDATE orders SET status = 'taken', executor_id = ?, taken_at = ? "
                "WHERE id = ? AND status = 'open'",
                (executor_id, now_iso(), order_id),
            )
            await self.conn.commit()
            changed = cur.rowcount
            await cur.close()
            return changed == 1

    async def set_order_status(self, order_id: int, status: str) -> None:
        await self._execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))

    async def count_today_orders(self, customer_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE customer_id = ? AND created_at >= ?",
            (customer_id, today_start_iso()),
        )
        return int(row["c"]) if row else 0

    async def count_active_orders(self, executor_id: int) -> int:
        """Hozir bajarilayotgan (taken) buyurtmalar soni."""
        row = await self._fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE executor_id = ? AND status = 'taken'",
            (executor_id,),
        )
        return int(row["c"]) if row else 0

    async def count_completed_orders(self, executor_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE executor_id = ? AND status = 'done'",
            (executor_id,),
        )
        return int(row["c"]) if row else 0

    async def get_orders_by_customer(self, customer_id: int, limit: int = 5) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT ?",
            (customer_id, limit),
        )

    async def get_orders_by_executor(self, executor_id: int, limit: int = 5) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM orders WHERE executor_id = ? ORDER BY id DESC LIMIT ?",
            (executor_id, limit),
        )

    async def get_last_orders(self, limit: int = 10) -> list[dict]:
        return await self._fetchall("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))

    async def count_orders_by_status(self) -> dict[str, int]:
        rows = await self._fetchall("SELECT status, COUNT(*) AS c FROM orders GROUP BY status")
        result = {"open": 0, "taken": 0, "done": 0, "cancelled": 0}
        for row in rows:
            result[str(row["status"])] = int(row["c"])
        return result

    async def count_orders(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM orders")
        return int(row["c"]) if row else 0

    async def get_expired_open_orders(self, minutes: int) -> list[dict]:
        """Muddati o'tgan va hali hech kim olmagan buyurtmalar."""
        return await self._fetchall(
            "SELECT * FROM orders WHERE status = 'open' AND timeout_notified = 0 "
            "AND created_at <= ? ORDER BY id",
            (minutes_ago_iso(minutes),),
        )

    async def mark_timeout_notified(self, order_id: int) -> None:
        await self._execute("UPDATE orders SET timeout_notified = 1 WHERE id = ?", (order_id,))

    async def reset_order_timer(self, order_id: int) -> None:
        """Qayta yuborish: yangi 30 daqiqalik oyn boshlanadi."""
        await self._execute(
            "UPDATE orders SET timeout_notified = 0, created_at = ? WHERE id = ?",
            (now_iso(), order_id),
        )

    # ---------------------------------------------------------- yuborilgan xabarlar
    async def save_order_message(
        self, order_id: int, executor_id: int, chat_id: int, message_id: int
    ) -> None:
        await self._execute(
            "INSERT INTO order_messages (order_id, executor_id, chat_id, message_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, executor_id, chat_id, message_id, now_iso()),
        )

    async def get_order_messages(self, order_id: int) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM order_messages WHERE order_id = ? ORDER BY id", (order_id,)
        )

    # ---------------------------------------------------------- baholar
    async def add_rating(
        self, order_id: int, executor_id: int, customer_id: int, score: int
    ) -> bool:
        """Baho qo'shadi (bitta buyurtma uchun faqat bitta baho). True = qo'shildi."""
        async with self.lock:
            cur = await self.conn.execute(
                "INSERT OR IGNORE INTO ratings (order_id, executor_id, customer_id, score, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, executor_id, customer_id, score, now_iso()),
            )
            await self.conn.commit()
            added = cur.rowcount
            await cur.close()
        if added:
            await self._execute(
                "UPDATE users SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 "
                "WHERE user_id = ?",
                (score, executor_id),
            )
            return True
        return False

    async def get_executor_rating(self, executor_id: int) -> tuple[float, int]:
        row = await self._fetchone(
            "SELECT rating_sum, rating_count FROM users WHERE user_id = ?", (executor_id,)
        )
        if not row:
            return 0.0, 0
        return float(row["rating_sum"] or 0), int(row["rating_count"] or 0)

    async def count_ratings(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS c FROM ratings")
        return int(row["c"]) if row else 0

    async def get_average_rating(self) -> float:
        row = await self._fetchone("SELECT AVG(score) AS a FROM ratings")
        if not row or row["a"] is None:
            return 0.0
        return float(row["a"])

    # ---------------------------------------------------------- shikoyatlar
    async def add_complaint(self, order_id: Optional[int], user_id: int, text: str) -> int:
        async with self.lock:
            cur = await self.conn.execute(
                "INSERT INTO complaints (order_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
                (order_id, user_id, text, now_iso()),
            )
            await self.conn.commit()
            cid = int(cur.lastrowid)
            await cur.close()
            return cid

    async def get_last_complaints(self, limit: int = 10) -> list[dict]:
        return await self._fetchall(
            "SELECT * FROM complaints ORDER BY id DESC LIMIT ?", (limit,)
        )


# global baza namunasi (butun bot shundan foydalanadi)
db = Database(DB_PATH)
