# https://github.com/reflex-dev/reflex/tree/main/docker-example/simple-one-port
# Now let's build the runtime image from the builder.
#   We'll just copy the env and the PATH reference.
FROM python:3.11-slim

ARG PORT=8080
ENV PORT=8080 API_URL=http://localhost:$PORT REDIS_URL=redis://localhost PYTHONUNBUFFERED=1
# Install Caddy and redis server inside image
# Also install gcc and libpq-dev for psycopg2 and unzip and curl for reflex
RUN apt-get update -y && apt-get install -y gcc libpq-dev unzip curl caddy redis-server && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY Caddyfile /app/Caddyfile
COPY reflex_lesssync /app/reflex_lesssync
COPY assets /app/assets
COPY rxconfig.py /app/rxconfig.py

WORKDIR /app

# Install app requirements and reflex in the container
RUN pip install -r requirements.txt

# Deploy templates and prepare app
RUN RX_INIT=1 reflex init

# Download all npm dependencies and compile frontend
RUN RX_INIT=1 reflex export --frontend-only --no-zip && mv .web/_static/* /srv/ && rm -rf .web

#ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
#ENV OPENAI_API_KEY=""

STOPSIGNAL SIGKILL

EXPOSE $PORT

# Apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
