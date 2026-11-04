# =============================================================================
# Legal Draft AI - Optimized Frontend Dockerfile
# =============================================================================
# Multi-stage build with optimized layers and caching
# =============================================================================

# ---- Stage 1: Builder ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies with better caching (only the runtime deps; Vite needs no
# extra build tools)
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --no-fund && npm cache clean --force

# Build with optimized Vite config
ARG VITE_API_URL
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
COPY . .
RUN npm run build

# ---- Stage 2: Production with Nginx ----
FROM nginx:alpine AS runtime

# Copy custom nginx config with optimizations
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:5173/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]