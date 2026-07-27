---
disable-model-invocation: true
---

# Bot Status Skill

Check which Chameleon bot services are running.

## Usage

`/bot-status`

## Actions

1. Check `pgrep -f run_bridge.py` for bridge
2. Check `pgrep -f "tsx watch src/index.ts"` for WhatsApp dev mode
3. Check `pgrep -f "node dist/index.js"` for production Telegram/WhatsApp
4. Check Docker status: `docker compose -f chameleon-bot/docker-compose.yaml ps`
5. Report running/PID status for each service
