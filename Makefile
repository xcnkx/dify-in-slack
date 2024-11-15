.PHONY: lint
lint:
	uv run ruff check .

.PHONY: fix
fix:
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: build-dev
build-dev:
	docker compose -f docker-compose.dev.yml up --build

.PHONY: deploy-prod
deploy-prod:
	sls deploy --stage prod --verbose