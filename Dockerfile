FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data PORT=8080
WORKDIR /app
RUN pip install --no-cache-dir pywebpush==2.0.3 tzdata==2026.2 reportlab==4.4.10 pypdf==6.6.0
RUN groupadd --gid 10001 campo && useradd --uid 10001 --gid campo --no-create-home campo && mkdir /data && chown campo:campo /data
COPY --chown=campo:campo server.py /app/server.py
COPY --chown=campo:campo telegram_bot.py /app/telegram_bot.py
COPY --chown=campo:campo public /app/public
COPY --chown=campo:campo backend /app/backend
COPY --chown=campo:campo frontend /app/frontend
USER campo
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"
CMD ["python", "server.py"]

FROM runtime AS test
COPY --chown=campo:campo tests /app/tests
COPY --chown=campo:campo deploy/activate-release.sh /app/deploy/activate-release.sh
ENV DATA_DIR=/tmp/campo-tests ERP_MODE=demo TELEGRAM_MODE=demo TELEGRAM_POLLING=false REMINDERS_ENABLED=false
CMD ["python", "-m", "unittest", "discover", "-s", "tests"]

FROM runtime AS production
