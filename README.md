# MedTender AI Agent

O'zbekistondagi medtexnika, laboratoriya, diagnostika, tibbiy buyumlar va tibbiy infratuzilma tenderlarini kuzatib, faol va mos tenderlarni Telegram orqali yuboradigan Python agent.

## MVP tarkibi

- `config/sources.yaml` orqali ustuvorlik bo'yicha sozlanadigan 22+ manba.
- Alohida parserlar: eTender UZEX, Xarid UZEX, SSV, O'zmedimpeks, UNGM, UNOPS, Farma UZEX, XT-Xarid, Xarid MF va generic parserlar.
- O'zbek, rus va ingliz keyword qidiruvi.
- Klassifikatsiya: Medical Equipment, Laboratory Equipment, Diagnostic Equipment, Medical Consumables, Hospital Infrastructure, Ambulance and Medical Transport, Installation and Commissioning, Pharmaceuticals, Not Relevant.
- SQLite modeli: tenders, tender_sources, notifications, source_runs, user_actions.
- Dublikat aniqlash va content hash orqali o'zgarishlarni topish.
- Deadline o'tgan yoki bekor qilingan tenderlarni yubormaslik.
- Deadline yaqinlashganda eslatma.
- Telegram Bot API: retry, MarkdownV2 escape, uzun xabarlarni bo'lish, inline tugmalar, admin buyruqlar.
- CLI, Docker, systemd timer, install script va pytest testlari.

## Muhim eslatma

Davlat xaridlari saytlarining HTML/API tuzilmasi o'zgarishi mumkin. Parserlar mustaqil modul qilingan: bitta manba o'zgarsa, faqat o'sha `app/parsers/*.py` faylini moslash kerak. CAPTCHA yoki login talab qilinadigan sahifalar avtomatik aylanib o'tilmaydi, xato log va hisobotda ko'rsatiladi.

## Lokal ishga tushirish

```bash
cd tender-parser
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

`.env` ichida Telegram qiymatlarini kiriting:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ADMIN_IDS=
TELEGRAM_THREAD_ID=
TZ=Asia/Tashkent
DATABASE_URL=sqlite:///./data/medtender.sqlite3
SOURCES_CONFIG_PATH=config/sources.yaml
```

Bir marta monitoring:

```bash
python -m app.main run
```

Telegram test:

```bash
python -m app.main test-telegram
```

Manbalarni test qilish:

```bash
python -m app.main test-sources
```

Telegram bot polling:

```bash
python -m app.main poll
```

Oxirgi runlar hisoboti:

```bash
python -m app.main report
```

Tenderni qayta yuborish:

```bash
python -m app.main resend --tender-id 123
```

## Telegram buyruqlari

Foydalanuvchi buyruqlari: `/start`, `/help`, `/status`, `/today`, `/latest`, `/search <so'z>`, `/deadlines`, `/categories`, `/mute <kategoriya>`, `/unmute <kategoriya>`, `/settings`.

Admin buyruqlari faqat `TELEGRAM_CHAT_ID` yoki `TELEGRAM_ADMIN_IDS` ichidagi chat/user ID uchun ishlaydi: `/run`, `/test_sources`, `/test_telegram`, `/resend <id>`, `/report`, `/cleanup`, `/pause`, `/resume`, `/errors`, `/addkeyword <til> <so'z>`, `/removekeyword <so'z>`, `/sources`.

Tender xabarlarida `Manbaga o'tish`, `To'liq ma'lumot`, `Saqlash`, `Kategoriyani mute`, `Mos emas` inline tugmalari bor. Deadline eslatmasida `Manbaga o'tish` va `Ko'rib chiqdim`; kunlik hisobotda `Batafsil hisobot` va `Xatoliklar` tugmalari yuboriladi.

## Docker

```bash
cp .env.example .env
chmod 600 .env
docker compose build
docker compose run --rm medtender
docker compose up -d medtender-bot
```

## Production install

Serverda:

```bash
sudo ./install.sh
sudo nano /opt/medtender-agent/.env
sudo systemctl start medtender.service
sudo systemctl status medtender-bot.service
```

Timer holati:

```bash
sudo systemctl status medtender.timer
sudo systemctl status medtender-afternoon.timer
```

Qo'lda ishga tushirish:

```bash
sudo systemctl start medtender.service
```

Loglar:

```bash
sudo journalctl -u medtender.service -n 200 --no-pager
```

## Testlar

```bash
pytest
```

Hozirgi avtomatik testlar:

- klassifikatsiya;
- dublikat kaliti va content hash;
- deadline validatsiyasi;
- umumiy HTML parser.
- source konfiguratsiyasi va eTender API normalizatsiyasi.

## Katalog tuzilmasi

```text
app/
  main.py
  config.py
  models/
  parsers/
  repositories/
  services/
  utils/
tests/
migrations/
requirements.txt
Dockerfile
docker-compose.yml
medtender.service
medtender-bot.service
medtender.timer
install.sh
```

## Xavfsizlik

- Telegram token kodga yozilmaydi.
- `.env` gitga kiritilmaydi.
- `.env` ruxsati `600` bo'lishi kerak.
- Production servis `medtender` user nomidan ishlaydi.
- Token, cookie, password va shunga o'xshash maxfiy qiymatlar logga yozilmaydi.
