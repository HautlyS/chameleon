FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY chameleon-bot/opencode-telegram-bot/package.json chameleon-bot/opencode-telegram-bot/package-lock.json ./chameleon-bot/opencode-telegram-bot/
RUN cd chameleon-bot/opencode-telegram-bot && npm ci

COPY requirements.txt ./
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt "rendercv[full]"

COPY . .
RUN cd chameleon-bot/opencode-telegram-bot && npm run build

ENV PYTHONPATH=/app
ENV CHAMELEON_PROJECT_ROOT=/app

CMD ["node", "chameleon-bot/opencode-telegram-bot/dist/index.js"]
