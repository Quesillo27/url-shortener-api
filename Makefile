install:
	pip install -r requirements.txt

run:
	uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --reload

test:
	pytest tests/ -v --tb=short

.PHONY: install run test
