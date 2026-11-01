FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LIBRAAI_ENV=production LIBRAAI_DB_PATH=/data/libraai.db
WORKDIR /app
COPY requirements-production.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt && useradd -m -u 10001 libra && mkdir -p /data && chown libra:libra /data
COPY . .
USER libra
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=3)" || exit 1
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "60", "app:app"]
