# 🤝 Frilans bozori Telegram boti

Buyurtmachi (ish beruvchi) va ijrochini (frilanser) bog'lovchi Telegram bot.
Butun interfeysi **o'zbek tilida**.

**Texnologiyalar:** Python 3.10+, aiogram 3.x, aiosqlite, python-dotenv.
Android'dagi **Pydroid 3**'da ham ishlaydi (og'ir kutubxonalar ishlatilmagan).

---

## 📂 Fayl tuzilmasi

```
bot/
  main.py            # ishga tushirish nuqtasi
  config.py          # sozlamalar + boshlang'ich sohalar/yo'nalishlar lug'ati
  database.py        # barcha SQL funksiyalar (PostgreSQL'ga o'tish uchun faqat shu fayl)
  states.py          # FSM holatlari
  keyboards.py       # inline klaviaturalar (sahifalash bilan)
  utils.py           # yordamchi funksiyalar (xato boshqaruvi, matn shakllantirish)
  handlers/
    start.py         # /start, /menu, rol tanlash
    executor.py      # ijrochi oqimi (soha → yo'nalishlar)
    customer.py      # buyurtmachi oqimi (FSM, qadamma-qadam)
    orders.py        # qabul qilish, muddat, yakunlash, baho, shikoyat, relay
    admin.py         # /stats, /broadcast, /addskill, /orders, /complaints
  services/
    dispatcher.py    # buyurtmani ijrochilarga tarqatish
    timeouts.py      # 30 daqiqalik muddat nazorati (fon vazifasi)
    gist_backup.py   # bazani GitHub Gist'ga nusxalash (bepul hosting uchun)
Dockerfile           # Render.com / Docker uchun
render.yaml          # Render.com bepul worker (24/7)
.github/workflows/bot.yml   # GitHub Actions bepul ishga tushirish
requirements.txt
.env.example
README.md
```

---

## ⚡ Tez ishga tushirish

### 1. Telegram bot yaratish
1. **@BotFather**'ga yozing → `/newbot` → nom va username bering.
2. BotFather sizga **token** beradi (masalan `123456:AAE...`).
3. O'zingizning **Telegram ID**'sini oling: **@userinfobot** → `/start` → ID.

### 2. Fayllarni yuklash
```bash
git clone <repo> frilans-bot
cd frilans-bot
```

### 3. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 4. `.env` faylini yaratish
```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS / Pydroid
```
`.env` ichini to'ldiring:
```env
BOT_TOKEN=123456:AAE...
ADMIN_ID=987654321
```

### 5. Ishga tushirish
```bash
python bot/main.py
```
yoki
```bash
python -m bot.main
```

> Birinchi ishga tushganda `bot_data.db` fayli yaratiladi va boshlang'ich
> 15 ta soha + 130+ yo'nalish bazaga yoziladi. Keyinchalik **baza asosiy manba** bo'lib qoladi.

---

## 📱 Foydalanish

### Ijrochi
1. `/start` → **👷 Men ijrochiman**
2. Soha tanlash → yo'nalish tanlash (ko'p tanlash mumkin, ✅ belgisi bilan)
3. **✅ Tayyor** → profilga saqlanadi
4. Keyinchalik **⚙️ Yo'nalishlarim** orqali o'zgartiriladi
5. Buyurtma kelganda **✅ Qabul qilaman** bosing

### Buyurtmachi
1. `/start` → **📝 Men buyurtmachiman**
2. Soha → yo'nalish → vazifa → byudjet → muddat
3. **✅ Yuborish** → buyurtma `open` holatida bazaga saqlanadi va tarqatiladi
4. Birinchi **✅ Qabul qilaman** degan ijrochi buyurtmani oladi
5. Ish tugagach **✅ Ish tugadi** → ⭐ 1–5 baho bering

### Admin buyruqlari (faqat `ADMIN_ID`)
| Buyruq | Vazifasi |
|---|---|
| `/stats` | foydalanuvchi, buyurtma, reyting statistikasi |
| `/broadcast` | barcha foydalanuvchilarga xabar (`/broadcast matn` shaklida ham) |
| `/addskill` | yangi soha/yo'nalish qo'shish (botni qayta ishga tushirmasdan) |
| `/orders` | oxirgi buyurtmalar ro'yxati |
| `/complaints` | kelgan shikoyatlar |
| `/admin` | yordamchi menyu |

`/addskill` ikki xil usulda ishlaydi:
```
/addskill                      → FSM: soha nomi → yo'nalish nomi
/addskill Soha | Yo'nalish     → bir buyruqda
```

---

## 🔁 Oqimlar (diagramma)

```
IJROCHI                                BUYURTMACHI
─────────                               ───────────
/start → 👷 Men ijrochiman              /start → 📝 Men buyurtmachiman
   ↓                                       ↓
Soha → Yo'nalish(lar) ✅ Tayyor         Soha → Yo'nalish → Vazifa
   ↓                                       ↓         → Byudjet → Muddat
Profilga saqlanadi ✅                        ↓      (Tasdiqlash ekrani)
   ↓                                       ↓
   │  ◀── 📬 Buyurtma xabari ────────────  │  (order = open, bazaga)
   │                                       │
   └── ✅ Qabul qilaman ──▶ ATOMIK UPDATE ─┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
        G'olibi "🔒 Band"          Buyurtmachi: ijrochi ismi +
        (xabar tahrirlanadi)      username (yo'q bo'lsa → relay)
```

```
🔁 Qayta yuborish        ❌ Bekor qilish        ⌛ 30 daqiqa
   ↺ Yana 30 daqiqa        ✖ status=cancelled    ⏱ Fon vazifasi tekshiradi
```

---

## ⚙️ Cheklovlar va qoidalar

| Qoida | Qiymat (`.env`) |
|---|---|
| Bir buyurtmachi kunida maksimal buyurtma | `DAILY_ORDER_LIMIT=5` |
| Bir ijrochi faol buyurtmalar soni | `MAX_ACTIVE_ORDERS=3` |
| Ijrochi topilmasa kutish vaqti | `ORDER_TIMEOUT_MINUTES=30` |
| Xabarlar orasidagi pauza (Telegram limit) | `SEND_DELAY=0.05` |

**Poyga holatidan himoya:** qabul qilish bitta atomik SQL so'rovi bilan bajariladi
(`UPDATE orders SET status='taken' ... WHERE id=? AND status='open'`), shuning uchun
ikki ijrochi bir vaqtda bosganida faqat bittasi yutadi — qolganiga
*"Kech qoldingiz, buyurtmani boshqa ijrochi oldi"* deb xabar beriladi.

**Username yo'q bo'lsa:** bot orqali yozish (relay) rejimi yoqiladi —
`https://t.me/<bot>?start=r<order_id>_e` havolasi orqali xabarlar bir-biriga uzatiladi.

**Muddat nazorati:** `asyncio` fon vazifasi har 30 sekundda `open` holatidagi
buyurtmalarni tekshiradi; bot qayta ishga tushganda ham nazorat tiklanadi.

---

## 🗄️ Baza jadvallari

| Jadval | Ustunlar |
|---|---|
| `users` | user_id, username, full_name, role, rating_sum, rating_count, is_active, created_at |
| `categories` | id, name |
| `skills` | id, category_id, name |
| `executor_skills` | user_id, skill_id |
| `orders` | id, customer_id, skill_id, skill_name, description, budget, deadline, status, executor_id, is_custom, timeout_notified, customer_chat_id, customer_message_id, created_at, taken_at |
| `order_messages` | id, order_id, executor_id, chat_id, message_id, created_at |
| `ratings` | id, order_id, executor_id, customer_id, score, created_at |
| `complaints` | id, order_id, user_id, text, created_at |

`status`: `open` → `taken` → `done` (yoki `cancelled`).

PostgreSQL'ga o'tish uchun faqat `bot/database.py` faylidagi SQL'ni almashtirish kifoya —
handlerlar baza qatlamiga faqat shu modul orqali muroqat qiladi.

---

## 📱 Pydroid 3 (Android)

1. Pydroid 3'ni Play Store'dan o'rnating.
2. Pip oynasida **Pip** → **Termux**/`bash` → `pip install aiogram aiosqlite python-dotenv`.
3. Loyiha fayllarini telefonga (masalan `/storage/emulated/0/Download/bot/`) nusxalang.
4. `.env` faylini ham o'sha papkaga qo'ying.
5. Terminalda:
   ```bash
   cd /storage/emulated/0/Download/bot
   python bot/main.py
   ```
6. Telefon quvvatga ulangan holda bot ishlayveradi (fon rejimida ham).

> `python-dotenv` `.env` faylni loyiha papkasida, joriy papkada yoki `bot/` ichida qidiradi.

---

## 🚂 Railway'ga joylash

1. **Railway.app** → GitHub repo'ni ulang (yoki `New Project → Deploy from GitHub repo`).
2. **Variables** bo'limiga o'ting va qo'shing:
   ```
   BOT_TOKEN=123456:AAE...
   ADMIN_ID=987654321
   ```
   (`DB_PATH` ixtiyoriy — default `/data/bot_data.db` qilib belgilash mumkin)
3. **Settings → Deploy → Custom Start Command**:
   ```
   python bot/main.py
   ```
4. **Settings → Volumes** → yangi volume yarating va mount path: `/data`
   (baza fayl saqlanadi, redeploy'da o'chib ketmaydi).
5. **Deploy** bosing. Loglarda `Bot ishga tushdi: @your_bot` yozuvini ko'rasiz.

**Render.com** uchun:
- Build: `pip install -r requirements.txt`
- Start: `python bot/main.py`
- Environment: `BOT_TOKEN`, `ADMIN_ID`
- Disk: `/data` ga ulab, `DB_PATH=/data/bot_data.db`

**Docker** (ixtiyoriy) — `Dockerfile` loyihada tayyor:
```bash
docker build -t frilans-bot .
docker run -d --name frilans-bot --env-file .env frilans-bot
```

---

## 🆓 BEPUL 24/7 (karta talab qilinmaydi)

Ikkala variant ham **$0**, karta kerak emas:

| | Render.com (worker) | GitHub Actions (public repo) |
|---|---|---|
| Ishlash | Doimiy (uxlamaydi) | Har 13 daqiqada qayta ishga tushadi |
| Karta | ✅ kerak emas | ✅ kerak emas |
| Cheklov | Bepul instans darajasi | Public repo'da daqiqlar cheksiz |
| Baza | GitHub Gist (bepul, doimiy) | GitHub Gist (bepul, doimiy) |

### Variant 1 — Render.com (tavsiya etiladi)

1. **GitHub**'da repo'ni oching va kodni `git push` qiling (`bot_data.db` kerak emas).
2. **[render.com](https://render.com)** → GitHub bilan kiring (karta talab qilinmaydi).
3. **New + → Background Worker** (Web Worker EMAS!) → repo'ni tanlang → Runtime: **Docker**.
4. **Environment** qo'shing:

   | Kalit | Qiymat |
   |---|---|
   | `BOT_TOKEN` | `88147...:AAE...` |
   | `ADMIN_ID` | sizning Telegram ID |
   | `GIST_TOKEN` | GitHub PAT (5-qadam) |
   | `DB_PATH` | `/app/bot_data.db` |

5. **Gist tokeni** (baza uchun): GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → **Generate new token (classic)** → scope: **gist** ✓ → yarating.
6. **Deploy** bosing. Logda `🆕 Yangi Gist yaratildi` chiqadi — bu baza.
7. Render → **Logs** → `Bot ishga tushdi: @frelanserborbot` ni tekshiring.

> Render bepul worker **uxqubormaydi** (sleep yo'q) — bot haqiqatan 24/7 ishlaydi.

### Variant 2 — GitHub Actions (public repo)

1. Repo'ni GitHub'ga **public** qilib yuklang.
2. **Settings → Secrets and variables → Actions** → **New repository secret**:
   `BOT_TOKEN`, `ADMIN_ID`, `GIST_TOKEN`.
3. **Actions** → **Frilans bot** → **Run workflow**.
4. Har 13 daqiqada bot qayta ishga tushadi; bazani Gist'dan o'qib, qaytadi.

> Private repo'da bepul 2000 daqiqa/oy (≈154 ishga tushirish) — shuning uchun public repo tavsiya etiladi.

### Baza qayerda saqlanadi?

Render bepul instansiyasining diski vaqtincha (deploy'da o'chadi). Shuning uchun
`bot/services/gist_backup.py` baza faylini **GitHub Gist**'ga nusxalaydi:

* har `GIST_INTERVAL_MINUTES` daqiqada + bot to'xtaganda
* bot ishga tushganda Gist'dan qayta yuklaydi

`GIST_TOKEN` bo'sh bo'lsa — Gist o'chirilgan bo'ladi, lokal fayl ishlatiladi.

---

## 🔧 Sozlamalar (.env)

| O'zgaruvchi | Tavsif | Default |
|---|---|---|
| `BOT_TOKEN` | BotFather tokeni (majburiy) | — |
| `ADMIN_ID` | Admin Telegram ID | `0` |
| `DB_PATH` | SQLite fayl yo'li | `bot_data.db` |
| `DAILY_ORDER_LIMIT` | Kunlik buyurtma limiti | `5` |
| `MAX_ACTIVE_ORDERS` | Faol buyurtma limiti | `3` |
| `ORDER_TIMEOUT_MINUTES` | Ijrochi kutish vaqti (daqiqa) | `30` |
| `PAGINATION_SIZE` | Sahifadagi tugmalar soni | `8` |
| `SEND_DELAY` | Xabarlar orasidagi pauza (s) | `0.05` |
| `TZ_OFFSET_HOURS` | Mahalliy vaqt (UTC+5 = O'zbekiston) | `5` |
| `ADMIN_NOTIFY_ALL` | Barcha buyurtmalarni admin'ga yuborish | `1` |
| `GIST_TOKEN` | GitHub PAT — baza nusxasi uchun | bo'sh (o'chiq) |
| `GIST_ID` | Gist ID (avtomatik yoziladi) | bo'sh |
| `GIST_INTERVAL_MINUTES` | Baza nusxasi oraliq (daqiqa) | `5` |
| `MAX_RUNTIME_MINUTES` | Maksimal ish vaqti (Actions uchun) | `0` (cheksiz) |

---

## ❓ Tez-tez uchraydigan savollar

**Tugmalar ishlamayapti?**
Tugmalar eski xabarda qolib qolsa — botni qayta ishga tushiring va `/start` bosing.
Har bir tugma ma'lumot bazadagi ID bilan bog'langan, shuning uchun eskirgan xabarlar ishlamaydi.

**Buyurtma hech kimga yuborilmaydi?**
`/stats` orqali buyurtmalar sonini tekshiring. Ehtimol bu yo'nalishni tanlagan faol ijrochi yo'q —
bunda buyurtma avtomatik admin'ga yuboriladi va u `📣 Eksecutorlarga yuborish` tugmasi bilan
qo'lda tarqatadi.

**Bazani tozalash?**
`bot_data.db` faylini o'chirib, botni qayta ishga tushiring — baza qaytadan yaratiladi
(katalog `config.py` dan qayta yoziladi).
