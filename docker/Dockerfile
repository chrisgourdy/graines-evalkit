# EVALKIT — one image, four modes: cli (default) | api | worker | scheduler
# Build (CI only, see docs/DISTRIBUTION.md):
#   docker buildx build -f docker/Dockerfile --platform linux/amd64,linux/arm64 -t graines/evalkit:dev .
# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /wheels

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EVALKIT_DATA_DIR=/data EVALKIT_PROJECTS_DIR=/projects
RUN groupadd --gid 10001 evalkit && useradd --uid 10001 --gid evalkit --create-home --shell /usr/sbin/nologin evalkit \
    && mkdir -p /data /projects && chown -R evalkit:evalkit /data /projects
COPY --from=build /wheels/*.whl /tmp/
RUN pip install --no-cache-dir "$(ls /tmp/*.whl)[api,http]" && rm -f /tmp/*.whl
COPY --chown=evalkit:evalkit docker/entrypoint.sh /usr/local/bin/evalkit-entrypoint
COPY --chown=evalkit:evalkit scenarios/examples/demo /projects/demo
COPY --chown=evalkit:evalkit prices /opt/evalkit/prices
RUN chmod +x /usr/local/bin/evalkit-entrypoint
USER evalkit
WORKDIR /data
VOLUME ["/data", "/projects"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["evalkit", "version"]
ENTRYPOINT ["evalkit-entrypoint"]
CMD ["cli", "version"]
