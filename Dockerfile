FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG APP_UID=1000
ARG APP_GID=1000

RUN groupadd --gid "${APP_GID}" vbondarev \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin vbondarev \
    && mkdir -p /data \
    && chown vbondarev:vbondarev /app /data

COPY --chown=vbondarev:vbondarev app ./app
COPY --chown=vbondarev:vbondarev scripts ./scripts

USER vbondarev

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
