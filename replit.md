# IBEKS Telegram Bot

## Run

The `IBEKS` console workflow runs:

```bash
python3 main.py
```

The launcher starts the manager bot, which manages the userbot runner.

## Required Replit Secrets

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `STRING_SESSION`

`OWNER_ID` is a non-secret shared environment setting. The project uses local SQLite databases by default. Optional AI and voice features additionally use the keys documented in `.env.example`.