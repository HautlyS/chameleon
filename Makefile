VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

ifeq ($(OS),Windows_NT)
	PYTHON := $(VENV)/Scripts/python.exe
	PIP := $(VENV)/Scripts/pip.exe
endif

install-tools:
	python3 -m venv $(VENV)
	$(PIP) install --quiet "rendercv[full]"
	@echo "rendercv installed."

# Full setup — install everything needed
setup:
	@echo "[Chameleon Setup]"
	@echo ""
	@echo "[1/5] Creating virtual environment..."
	python3 -m venv $(VENV) 2>/dev/null || true
	@echo "[2/5] Installing core dependencies..."
	$(PIP) install --quiet textual pyyaml httpx reportlab beautifulsoup4 lxml markdownify
	@echo "[3/5] Installing RenderCV..."
	$(PIP) install --quiet "rendercv[full]" || true
	@echo "[4/5] Installing Playwright (browser automation)..."
	$(PIP) install --quiet playwright || true
	$(PYTHON) -m playwright install chromium 2>/dev/null || echo "  (Chromium install deferred)"
	@echo "[5/5] Creating default config..."
	mkdir -p .chameleon output/job_analyses output/cover_letters
	@echo ""
	@echo "Setup complete! Run: make list-platforms  or  ./chameleon tui"

# Install Playwright browser automation (for LinkedIn/Indeed/Wellfound)
install-playwright:
	$(PIP) install --quiet playwright
	$(PYTHON) -m playwright install chromium
	@echo "Playwright + Chromium installed. Blocked job sites (LinkedIn, Indeed, etc.) will now work."

install-deps:
	$(PIP) install --quiet -r requirements.txt
	@echo "Python deps installed."

test:
	$(PYTHON) -m pytest tests/ -v --tb=short $(ARGS)

test-coverage:
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=scripts $(ARGS)

# Usage: make render FILE=templates/david_alecrim_cv.yaml
render:
	@test -n "$(FILE)" || (echo "Usage: make render FILE=<path>"; exit 1)
	$(PYTHON) scripts/render.py $(FILE)

# ── CLI Targets ──────────────────────────────────────────────────────────

# Tailor CV for a job (text, URL, or file)
# Usage: make tailor JD="Senior Rust Engineer at Acme..." COMPANY=Acme TITLE=Engineer
# Usage: make tailor JD=https://jobs.example.com/senior-rust
# Usage: make tailor JD=jd.txt
tailor:
	@test -n "$(JD)" || (echo "Usage: make tailor JD=<text_or_url_or_file> [COMPANY=X] [TITLE=Y]"; exit 1)
	./chameleon tailor "$(JD)" $(if $(COMPANY),--company "$(COMPANY)") $(if $(TITLE),--title "$(TITLE)")

# Score a job against profile
# Usage: make score JD="Python developer, Django..."
score:
	@test -n "$(JD)" || (echo "Usage: make score JD=<text_or_url_or_file>"; exit 1)
	./chameleon score "$(JD)" $(if $(CV),--cv "$(CV)")

# Scan job platforms
# Usage: make scan QUERY="rust engineer" PLATFORMS=remoteok,hn_hiring
# Usage: make scan-all
scan:
	./chameleon scan $(if $(QUERY),-q "$(QUERY)") $(if $(PLATFORMS),-p "$(PLATFORMS)") $(if $(LIMIT),-n $(LIMIT))

scan-all:
	./chameleon scan --all $(if $(QUERY),-q "$(QUERY)")

scan-tier1:
	./chameleon scan --tier1 $(if $(QUERY),-q "$(QUERY)")

# List available scanner platforms
list-platforms:
	./chameleon scan --list-platforms

# ── Bot Integration ──────────────────────────────────────────────────────

# Run the RSS scanner bridge
bot-bridge:
	$(PYTHON) chameleon-bot/run_bridge.py --rss

# Run one scan cycle
bot-scan:
	$(PYTHON) chameleon-bot/run_bridge.py --scan $(ARGS)

# Install Telegram bot dependencies
bot-telegram-setup:
	cd chameleon-bot/opencode-telegram-bot && npm install

# Build Telegram bot
bot-telegram-build:
	cd chameleon-bot/opencode-telegram-bot && npm run build

# Run Telegram bot (dev mode)
bot-telegram-dev:
	cd chameleon-bot/opencode-telegram-bot && npm run dev

# Install WhatsApp bot dependencies
bot-whatsapp-setup:
	cd chameleon-bot/whatsapp-bot && npm install

# Build WhatsApp bot
bot-whatsapp-build:
	cd chameleon-bot/whatsapp-bot && npm run build

# Run WhatsApp bot (dev mode)
bot-whatsapp-dev:
	cd chameleon-bot/whatsapp-bot && npm run dev

# Start full bot stack via Docker Compose
bot-up:
	docker compose -f chameleon-bot/docker-compose.yaml up -d

# Stop full bot stack
bot-down:
	docker compose -f chameleon-bot/docker-compose.yaml down

# View bot logs
bot-logs:
	docker compose -f chameleon-bot/docker-compose.yaml logs -f
