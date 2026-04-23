install:
	python3 -m pip install -r requirements.txt

dev:
	uvicorn main:app --host 0.0.0.0 --port $${PORT:-8000} --reload

run:
	uvicorn main:app --host 0.0.0.0 --port $${PORT:-8000}

test:
	pytest tests/ -v --tb=short

build:
	python3 -m compileall app main.py

docker:
	docker build -t url-shortener-api .

lint:
	python3 -m compileall app main.py

.PHONY: install dev run test build docker lint
