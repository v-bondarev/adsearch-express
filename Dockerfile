FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN groupadd --gid "${APP_GID}" vbondarev \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin vbondarev \
    && mkdir -p /data \
    && chown -R vbondarev:vbondarev /app /data

USER vbondarev

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
