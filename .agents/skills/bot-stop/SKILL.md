---
disable-model-invocation: true
---

# Bot Stop Skill

Stop Chameleon bot services.

## Usage

`/bot-stop [service]`

Services:
- `bridge` — Stop RSS scanner
- `telegram` — Stop Telegram bot  
- `whatsapp` — Stop WhatsApp bot
- *(no arg)* — Stop all services

## Actions

1. Find the PID of the running service (e.g., `pgrep -f run_bridge.py` for bridge)
2. Send SIGTERM
3. Confirm the process exited
