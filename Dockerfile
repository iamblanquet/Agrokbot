FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data PORT=8080
WORKDIR /app
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
