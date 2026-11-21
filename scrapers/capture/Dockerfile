# Sandboxed capture worker: Playwright's official image, non-root, read-only rootfs, writes only to /out.
#
#   docker build -t redpill-capture -f scrapers/capture/Dockerfile .
#   docker run --rm --read-only --tmpfs /tmp --tmpfs /home/pwuser/.cache --cap-drop ALL \
#     --security-opt no-new-privileges --memory 2g --pids-limit 512 \
#     -v %cd%/data/captures:/out redpill-capture https://example.com --out /out --no-db
#
# Run it on a network that can reach the internet (or an egress proxy) but NOT internal ranges
# (Docker network with an egress firewall / --network=capture_egress), so a hostile page cannot pivot
# into the analyst LAN. Inside the container Chromium runs without its own sandbox (Docker seccomp blocks the
# namespaces it needs); the container (non-root, read-only, no caps) is the isolation boundary.
# Dev tip: mount the working tree over the baked code with -v <repo>/scrapers:/app/scrapers:ro.
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app
COPY scrapers/requirements.txt /app/scrapers/requirements.txt
# pin playwright to the base image version: its browsers in /ms-playwright belong to that release
RUN pip install --no-cache-dir -r /app/scrapers/requirements.txt "playwright==1.58.0"
COPY scrapers /app/scrapers

USER pwuser
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "scrapers.capture"]
