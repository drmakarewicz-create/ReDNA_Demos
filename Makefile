.PHONY: up down logs

COMPOSE ?= docker compose

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f
