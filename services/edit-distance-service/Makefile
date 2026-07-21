.PHONY: prep build test lint start clean docker-build generate-openapi dev prod

prep:
	pip install -e ".[dev,graph]"

build:
	pip install -e ".[graph]"

test:
	pytest -v

lint:
	ruff check src/
	ruff format --check src/

start:
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	rm -rf __pycache__ src/__pycache__ src/**/__pycache__
	rm -rf .venv venv
	rm -rf *.egg-info

generate-openapi:
	python -c "from src.main import app; import json; from fastapi.openapi.utils import get_openapi; spec = get_openapi(title=app.title, version=app.version, openapi_version=app.openapi_version, description=app.description, routes=app.routes); print(json.dumps(spec, indent=2))" > edit-distance-service.openapi.json

docker-build:
	docker build -t edit-distance-service .

dev:
	docker-compose -f docker-compose.dev.yml up --build

prod:
	docker-compose -f docker-compose.prod.yml up --build