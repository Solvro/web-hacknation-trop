# Sandboxed capture worker: Playwright's official image, non-root, read-only rootfs, writes only to /out.
# Build context = backend/ :
#   docker build -t trop-capture -f trop/capture/Dockerfile .        (done automatically by `trop capture`)
# Run (what `trop capture` does):
#   docker run --rm --read-only --tmpfs /tmp --tmpfs /home/pwuser --cap-drop ALL --security-opt no-new-privileges \
#     --memory 2g --pids-limit 512 --shm-size 512m -v "$PWD/../data/captures:/out" trop-capture <url> --out /out
#
# Run it on a network that can reach the internet (or an egress proxy) but NOT internal ranges, so a hostile page
# cannot pivot into the analyst LAN. Inside the container Chromium runs without its own sandbox (Docker's seccomp
# blocks the namespaces it needs); the container (non-root, read-only, no caps) is the isolation boundary.
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app
# pin playwright to the base image version: its browsers in /ms-playwright belong to that release
RUN pip install --no-cache-dir "playwright==1.58.0" "tldextract>=5.1" "mmh3>=4.1" "certifi"
# only the capture package is shipped (stub `trop` parent so `python -m trop.capture.worker` resolves)
RUN mkdir -p /app/trop && touch /app/trop/__init__.py
COPY trop/capture /app/trop/capture

USER pwuser
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "trop.capture.worker"]
