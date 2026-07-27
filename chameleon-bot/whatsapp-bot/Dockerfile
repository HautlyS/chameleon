FROM node:20-slim AS build

WORKDIR /build
COPY chameleon-bot/whatsapp-bot/package.json ./
RUN npm install
COPY chameleon-bot/whatsapp-bot/tsconfig.json ./
COPY chameleon-bot/whatsapp-bot/src/ ./src/
RUN npm run build

FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY chameleon-bot/whatsapp-bot/package.json ./chameleon-bot/whatsapp-bot/
RUN cd chameleon-bot/whatsapp-bot && npm install --omit=dev

COPY requirements.txt ./
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt "rendercv[full]"
COPY --from=build /build/dist/ ./chameleon-bot/whatsapp-bot/dist/
COPY chameleon-bot/bridge/ ./chameleon-bot/bridge/
COPY scripts/ ./scripts/
COPY templates/ ./templates/

ENV PYTHONPATH=/app
ENV CHAMELEON_PROJECT_ROOT=/app
EXPOSE 3001

CMD ["node", "chameleon-bot/whatsapp-bot/dist/index.js"]
