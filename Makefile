DOCKER_USERNAME ?= xenchrarr

# Project directories and their image names
HUGIN_CORE_DIR       = hugin-core
HUGIN_CORE_IMAGE     = hugin-core

ECOFLOW_DIR          = ecoflow-monitor
ECOFLOW_IMAGE        = ecoflow-monitor

OVERLIA_DIR          = overlia_production_bot
OVERLIA_IMAGE        = overlia-power-bot

SMS_DIR              = sms-bot
SMS_IMAGE            = sms-hub

ORCHESTRATOR_DIR     = orchestrator
ORCHESTRATOR_IMAGE   = orchestrator

ORCH_FRONTEND_DIR    = orchestrator-frontend
ORCH_FRONTEND_IMAGE  = orchestrator-frontend

POWERSHELL_DIR       = powershell-runner
POWERSHELL_IMAGE     = powershell-runner

TELEGRAM_RELAY_DIR   = telegram_relay
TELEGRAM_RELAY_IMAGE = telegram-relay

PRINTER_HUB_DIR      = printer-hub
PRINTER_HUB_IMAGE    = printer-hub

.PHONY: auth build push build-% push-%

auth:
	docker login

# Individual build/push targets
build-hugin-core:
	docker build --tag ${DOCKER_USERNAME}/${HUGIN_CORE_IMAGE} ${HUGIN_CORE_DIR}

build-ecoflow-monitor:
	docker build --tag ${DOCKER_USERNAME}/${ECOFLOW_IMAGE} ${ECOFLOW_DIR}

build-overlia:
	docker build --tag ${DOCKER_USERNAME}/${OVERLIA_IMAGE} ${OVERLIA_DIR}

build-sms-bot:
	docker build --tag ${DOCKER_USERNAME}/${SMS_IMAGE} ${SMS_DIR}

build-orchestrator:
	docker build --tag ${DOCKER_USERNAME}/${ORCHESTRATOR_IMAGE} ${ORCHESTRATOR_DIR}

build-orchestrator-frontend:
	docker build --no-cache --tag ${DOCKER_USERNAME}/${ORCH_FRONTEND_IMAGE} -f ${ORCH_FRONTEND_DIR}/dockerfile ${ORCH_FRONTEND_DIR}

build-powershell-runner:
	docker build --tag ${DOCKER_USERNAME}/${POWERSHELL_IMAGE} ${POWERSHELL_DIR}

build-telegram-relay:
	docker build --tag ${DOCKER_USERNAME}/${TELEGRAM_RELAY_IMAGE} ${TELEGRAM_RELAY_DIR}

build-printer-hub:
	docker build --tag ${DOCKER_USERNAME}/${PRINTER_HUB_IMAGE} ${PRINTER_HUB_DIR}

push-hugin-core:
	docker push ${DOCKER_USERNAME}/${HUGIN_CORE_IMAGE}

push-ecoflow-monitor:
	docker push ${DOCKER_USERNAME}/${ECOFLOW_IMAGE}

push-overlia:
	docker push ${DOCKER_USERNAME}/${OVERLIA_IMAGE}

push-sms-bot:
	docker push ${DOCKER_USERNAME}/${SMS_IMAGE}

push-orchestrator:
	docker push ${DOCKER_USERNAME}/${ORCHESTRATOR_IMAGE}

push-orchestrator-frontend:
	docker push ${DOCKER_USERNAME}/${ORCH_FRONTEND_IMAGE}

push-powershell-runner:
	docker push ${DOCKER_USERNAME}/${POWERSHELL_IMAGE}

push-telegram-relay:
	docker push ${DOCKER_USERNAME}/${TELEGRAM_RELAY_IMAGE}

push-printer-hub:
	docker push ${DOCKER_USERNAME}/${PRINTER_HUB_IMAGE}

# Build and push all
build: build-hugin-core build-ecoflow-monitor build-overlia build-sms-bot build-orchestrator build-orchestrator-frontend build-powershell-runner build-telegram-relay build-printer-hub

push: push-hugin-core push-ecoflow-monitor push-overlia push-sms-bot push-orchestrator push-orchestrator-frontend push-powershell-runner push-telegram-relay push-printer-hub
