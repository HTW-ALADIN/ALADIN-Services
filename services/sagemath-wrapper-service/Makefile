.PHONY: prep test lint start clean docker-build docker-run generate-openapi

SERVICE := sagemath-wrapper

prep:
	@pip install -e ".[test]"

test:
	@python -m pytest tests/

lint:
	@ruff check src/ tests/

start:
	@sage -python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	@rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-build:
	@docker build -t $(SERVICE) .

docker-run:
	@docker run --rm -p 8000:8000 $(SERVICE)

generate-openapi:
	@python scripts/export_openapi.py --out openapi/openapi.yaml