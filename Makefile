# Convenience shortcuts. Everything here is plain docker compose / npm / pytest.

COMPOSE      := docker compose
COMPOSE_E2E  := $(COMPOSE) -f docker-compose.yml -f e2e/docker-compose.e2e.yml
COMPOSE_OSRM := $(COMPOSE) -f docker-compose.yml -f docker-compose.osrm.yml

.PHONY: up offline down logs test test-backend test-frontend lint e2e clean

up:            ## Build and start the game on http://localhost:8080
	$(COMPOSE) up -d --build --wait
	@echo "\n  ▶ Open http://localhost:8080\n"

offline:       ## Same, with a local OSRM (first run downloads map data)
	$(COMPOSE_OSRM) up -d --build
	@echo "\n  ▶ Open http://localhost:8080 (routing is ready once 'osrm' is up: make logs)\n"

down:          ## Stop everything
	$(COMPOSE_OSRM) down --remove-orphans

logs:          ## Follow logs
	$(COMPOSE_OSRM) logs -f

test: test-backend test-frontend  ## Run all unit & integration tests (in Docker, no local toolchain needed)

test-backend:
	docker build -q --target test -t high-lander-tech-test-backend-test backend
	docker run --rm high-lander-tech-test-backend-test

test-frontend:
	docker run --rm -v "$(CURDIR)/frontend:/app" -w /app node:22-alpine \
		sh -c "npm ci --no-audit --no-fund && npm run typecheck && npm test"

e2e:           ## Start the stack with a stub router and play a scripted game against it
	$(COMPOSE_E2E) up -d --build --wait
	docker run --rm --network high-lander-tech-test_default -v "$(CURDIR)/e2e:/e2e:ro" python:3.12-slim \
		sh -c "pip install -q -r /e2e/requirements.txt && python /e2e/smoke_test.py http://frontend:8080"
	$(COMPOSE_E2E) down

clean:         ## Stop everything and delete volumes (incl. downloaded map data)
	$(COMPOSE_OSRM) down -v --remove-orphans
