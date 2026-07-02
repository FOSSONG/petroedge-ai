.PHONY: backend-test frontend-test lint up down generate replay

backend-test:
	cd backend && pytest

frontend-test:
	cd frontend && npm test -- --run

lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint

up:
	docker compose up --build

down:
	docker compose down

generate:
	python scripts/generate_synthetic_data.py --rows 1000 --out data/generated_well_logs.csv

replay:
	python scripts/replay_las.py --file data/sample_well.las --api http://localhost:8000

