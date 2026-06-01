.PHONY: setup build run dev clean

setup:
	@echo "--- Creating Python virtual environment ---"
	python3 -m venv .venv
	@echo "--- Installing Python dependencies ---"
	.venv/bin/pip install -q -r requirements.txt
	@echo "--- Installing Playwright browser ---"
	.venv/bin/playwright install chromium
	@echo "--- Installing frontend dependencies ---"
	cd frontend && npm install
	@echo "--- Copying .env template ---"
	@cp -n .env.example .env 2>/dev/null && echo "Created .env — fill in your credentials" || echo ".env already exists, skipping"
	@echo ""
	@echo "Setup complete. Edit .env with your credentials, then run: make run"

build:
	cd frontend && npm run build

run: build
	@echo "Starting mackbot at http://localhost:8000"
	.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000

dev:
	@echo "Starting backend at http://localhost:8000"
	.venv/bin/uvicorn server:app --reload &
	@echo "Starting frontend dev server at http://localhost:5173"
	cd frontend && npm run dev

clean:
	rm -rf .venv frontend/dist frontend/node_modules __pycache__
