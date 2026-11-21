# TROP web (Next.js standalone). Runtime image ~330 MB (node:24-alpine LTS).
# Build:  docker build -t trop-web web/
# Run:    docker run -p 127.0.0.1:13000:13000 -e API_INTERNAL_URL=http://api:18000 trop-web
# API_INTERNAL_URL is read at runtime by the /api/v1 proxy route (SSE streamed through).
# NEXT_PUBLIC_MOCK=1 (build arg) bakes in the offline fixture mode (no backend needed).
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:24-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_MOCK=0
ENV NEXT_PUBLIC_MOCK=$NEXT_PUBLIC_MOCK NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=13000 HOSTNAME=0.0.0.0 API_INTERNAL_URL=http://api:18000
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 13000
CMD ["node", "server.js"]
