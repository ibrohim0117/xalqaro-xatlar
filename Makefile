# Xalqaro xatlar — tez-tez ishlatiladigan buyruqlar.
# Ishlatish: make <nom>. Ro'yxat: make help
#
# Odatiy ish:
#   make start   — VLM va veb sahifani birga ishga tushiradi (Ctrl+C — ikkalasi ham to'xtaydi)
#   yoki ikki terminalda alohida:  make vlm   va   make web
# Sahifa: http://127.0.0.1:8000

VLM_PORT ?= 8090
WEB_PORT ?= 8000
VLM_LOG := outputs/vlm_server.log

.PHONY: help install vlm web start stop test lint model model-all eval

help:  ## buyruqlar ro'yxati
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install:  ## kutubxonalarni o'rnatish (Poetry; VLM muhiti — scripts/ocr/vlm_server.sh ichidagi yo'riqnoma)
	poetry install

vlm:  ## VLM serveri (127.0.0.1:8090), shu terminalda; to'xtatish — Ctrl+C
	VLM_PORT=$(VLM_PORT) sh scripts/ocr/vlm_server.sh

web:  ## veb sahifa va API (http://127.0.0.1:8000); VLM'ni avval ishga tushiring
	poetry run uvicorn src.web.api:app --host 127.0.0.1 --port $(WEB_PORT)

# VLM fonda ishga tushadi (log — outputs/vlm_server.log), u javob bera boshlagach (/health,
# ko'pi bilan ~2 daqiqa) sahifa ochiladi. Terminal yopilsa yoki Ctrl+C — VLM ham to'xtatiladi.
start:  ## VLM + veb sahifa birga (Ctrl+C — ikkalasi ham to'xtaydi)
	@mkdir -p outputs
	@VLM_PORT=$(VLM_PORT) sh scripts/ocr/vlm_server.sh > $(VLM_LOG) 2>&1 & VLM_PID=$$!; \
	trap 'kill $$VLM_PID 2>/dev/null' EXIT INT TERM; \
	echo "VLM yuklanmoqda (log: $(VLM_LOG))…"; \
	for i in $$(seq 60); do \
		curl -sf http://127.0.0.1:$(VLM_PORT)/health > /dev/null && break; \
		kill -0 $$VLM_PID 2>/dev/null || { echo "VLM ishga tushmadi — logni ko'ring: $(VLM_LOG)"; exit 1; }; \
		sleep 2; \
	done; \
	curl -sf http://127.0.0.1:$(VLM_PORT)/health > /dev/null \
		&& echo "VLM tayyor. Sahifa: http://127.0.0.1:$(WEB_PORT)" \
		|| echo "VLM hali javob bermadi — sahifa VLM'siz ishlaydi (qo'lyozma sana/raqam o'qilmaydi)"; \
	poetry run uvicorn src.web.api:app --host 127.0.0.1 --port $(WEB_PORT)

stop:  ## fonda qolib ketgan VLM va veb serverlarni to'xtatish
	@for port in $(VLM_PORT) $(WEB_PORT); do \
		pids=$$(lsof -ti tcp:$$port -sTCP:LISTEN 2>/dev/null); \
		if [ -n "$$pids" ]; then kill $$pids && echo "$$port-port to'xtatildi"; \
		else echo "$$port-port bo'sh"; fi; \
	done

test:  ## barcha testlar (real ma'lumotsiz)
	poetry run pytest -q

lint:  ## kod tekshiruvi va formatlash (ruff)
	poetry run ruff check . && poetry run ruff format .

model:  ## dev 70 xatdan model + LOO javoblari (outputs/model.json, outputs/b4/)
	poetry run python -m scripts.prototype.run_predict

model-all:  ## eski 100 xatning hammasidan model (yangi xatlar uchun)
	poetry run python -m scripts.prototype.build_model_all

eval:  ## dev LOO javoblarini baholash (avval: make model)
	poetry run python -m src.evaluation.evaluate outputs/b4
