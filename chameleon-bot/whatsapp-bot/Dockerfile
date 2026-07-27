FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY chameleon-bot/whatsapp-bot/package.json ./whatsapp-bot/
RUN cd chameleon-bot/whatsapp-bot && npm install --production

COPY chameleon-bot/whatsapp-bot/tsconfig.json ./whatsapp-bot/
COPY chameleon-bot/whatsapp-bot/src/ ./whatsapp-bot/src/

RUN cd chameleon-bot/whatsapp-bot && npm run build

COPY chameleon-bot/bridge/ ./chameleon-bot/bridge/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app

EXPOSE 3001

CMD ["node", "chameleon-bot/whatsapp-bot/dist/index.js"]
