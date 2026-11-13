# Viral research backend (API + worker).
# Build from the repo root, since the backend imports tools.loop:
#   docker build -f tools/app/backend/Dockerfile -t aibrand-backend .
#   docker run -p 8765:8765 --env-file tools/app/backend/.env \
#     -e GLASSER_API_KEY=... -e ANTHROPIC_API_KEY=... aibrand-backend
FROM python:3.12-slim-bookworm

# Node for the glasser CLI and the ACP harness CLIs (opencode, npx adapters).
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @glasser-ai/cli@latest opencode-ai@latest && npm cache clean --force

RUN pip install --no-cache-dir openpyxl yt-dlp imageio-ffmpeg "psycopg[binary,pool]" boto3 google-genai

# Speech-to-text on Linux uses transformers Qwen3-ASR (CPU). WITH_ASR=0 skips it for a much smaller image.
ARG WITH_ASR=1
RUN if [ "$WITH_ASR" = "1" ]; then \
      pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
      && pip install --no-cache-dir "transformers>=5.13" accelerate soundfile librosa; \
    fi

# Dirs exist up front (app-owned) so credential files and the HF model cache volume can be mounted into them.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /home/app/.config/glasser /home/app/.local/share/opencode /home/app/.cache/huggingface \
    && chown -R app /home/app

WORKDIR /app
RUN mkdir -p /app/local/aibrand/temp /app/local/app-runs && chown -R app /app/local
COPY --chown=app tools/common tools/common
COPY --chown=app tools/facebook_agent tools/facebook_agent
COPY --chown=app tools/loop tools/loop
COPY --chown=app tools/app/backend tools/app/backend
COPY --chown=app tools/app/browser-app/dist tools/app/browser-app/dist

USER app
ENV PYTHONUNBUFFERED=1 \
    VIRAL_APP_AGENT=opencode \
    ROLE=all \
    PORT=8765
EXPOSE 8765

# tini reaps agent/ffmpeg processes orphaned when Stop kills a job.
ENTRYPOINT ["tini", "--"]
# ROLE: all | api | worker. PORT is honoured for Cloud Run.
CMD ["sh", "-c", "exec python tools/app/backend/server.py --host 0.0.0.0 --port \"$PORT\" --role \"$ROLE\""]
