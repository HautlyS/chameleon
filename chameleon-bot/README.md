# Chameleon Bot Stack

Telegram + WhatsApp integration for the Chameleon resume tailor system.

## Components

| Component | Directory | Purpose |
|-----------|-----------|---------|
| **Bridge** | `bridge/` | Python bridge layer wrapping chameleon operations |
| **Telegram Bot** | `opencode-telegram-bot/` | Full-featured Telegram bot (grammY + OpenCode SDK) |
| **WhatsApp Bot** | `whatsapp-bot/` | Lightweight WhatsApp bot (Evolution API webhooks) |
| **RSS Scanner** | `bridge/rss_scanner.py` | Periodic job scanning with chat notifications |

## Quick Start

```bash
# 1. Install chameleon tools
make install-tools

# 2. Copy and edit env
cp chameleon-bot/.env.example chameleon-bot/.env

# 3. Run RSS scanner (periodic job alerts)
make bot-bridge

# 4. Run Telegram bot (in another terminal)
make bot-telegram-dev

# 5. Run WhatsApp bot (in another terminal)
make bot-whatsapp-dev
```

## Docker Deployment

```bash
# Start all services
make bot-up

# Check logs
make bot-logs

# Stop all services
make bot-down
```

## Architecture

```
Telegram User ──> Telegram Bot ──> OpenCode SDK ──> Chameleon (OpenCode skills)
                         │
WhatsApp User ──> Evolution API ──> WhatsApp Bot ──> Python Bridge ──> chameleon scripts
                                                         │
                                                    RSS Scanner (periodic)
```

## Environment Variables

See `.env.example` for all config options. Key vars:

- `TELEGRAM_BOT_TOKEN` — Telegram bot token from @BotFather
- `TELEGRAM_ALLOWED_USER_IDS` — comma-separated Telegram user IDs
- `EVOLUTION_API_URL` — Evolution API base URL
- `EVOLUTION_API_KEY` — Evolution API auth key
- `RSS_SCAN_INTERVAL_MINUTES` — how often to scan for new jobs
