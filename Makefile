.PHONY: help aeat-prepare-certs aeat-handshake test-factura-service-logic test-protection test-protection-e2e

help:
	@echo "Targets disponibles:"
	@echo "  make aeat-prepare-certs P12=/ruta/certificate.p12 [P12_PASSWORD=secret]"
	@echo "  make aeat-handshake"
	@echo "  make test-factura-service-logic"
	@echo "  make test-protection"
	@echo "  make test-protection-e2e"

aeat-prepare-certs:
	@if [ -z "$(P12)" ]; then \
		echo "ERROR: define P12=/ruta/certificate.p12"; \
		exit 2; \
	fi
	@python backend/scripts/prepare_aeat_certs.py --p12 "$(P12)" $(if $(P12_PASSWORD),--password "$(P12_PASSWORD)",)

aeat-handshake:
	@python backend/scripts/test_aeat_connection.py

test-factura-service-logic:
	@ENVIRONMENT=development \
	DEV_MODE=true \
	SUPABASE_URL=https://test-project.supabase.co \
	SUPABASE_KEY=test-anon-key \
	SUPABASE_SERVICE_KEY=test-service-role-key \
	SUPABASE_JWT_SECRET=unit-test-jwt-secret-at-least-32-chars \
	JWT_SECRET_KEY=unit-test-app-jwt-secret-32-characters! \
	ENCRYPTION_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA= \
	pytest backend/tests/integration/test_factura_service_logic.py -q

test-protection:
	@ENVIRONMENT=development \
	DEV_MODE=true \
	SUPABASE_URL=https://test-project.supabase.co \
	SUPABASE_KEY=test-anon-key \
	SUPABASE_SERVICE_KEY=test-service-role-key \
	SUPABASE_JWT_SECRET=unit-test-jwt-secret-at-least-32-chars \
	JWT_SECRET_KEY=unit-test-app-jwt-secret-32-characters! \
	ENCRYPTION_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA= \
	pytest backend/tests/integration/test_api_protection.py -q

test-protection-e2e:
	@ENVIRONMENT=development \
	DEV_MODE=true \
	TESTING=false \
	SUPABASE_URL=https://test-project.supabase.co \
	SUPABASE_KEY=test-anon-key \
	SUPABASE_SERVICE_KEY=test-service-role-key \
	SUPABASE_JWT_SECRET=unit-test-jwt-secret-at-least-32-chars \
	JWT_SECRET_KEY=unit-test-app-jwt-secret-32-characters! \
	ENCRYPTION_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA= \
	SESSION_SECRET_KEY=unit-test-session-secret-32-characters \
	pytest backend/tests/integration/test_app_wiring_e2e.py -q
