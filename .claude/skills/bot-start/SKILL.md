---
disable-model-invocation: true
---

# Bot Start Skill

Start Chameleon bot services (bridge, Telegram, WhatsApp).

## Usage

`/bot-start [service]`

Services:
- `bridge` — Start the RSS scanner daemon (periodic job scanning + notifications)
- `telegram` — Start the Telegram bot (requires npm deps installed)
- `whatsapp` — Start the WhatsApp webhook receiver
- *(no arg)* — Start all services

## Actions

1. Verify the service is not already running (check `make bot-status` or `ps aux`)
2. For `bridge`: run `make bot-bridge` in background
3. For `telegram`: run `make bot-telegram-dev` in background
4. For `whatsapp`: run `make bot-whatsapp-dev` in background
5. Report the PID and confirm the service started
