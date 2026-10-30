# =============================================================================
# Legal Draft AI - Optimized Frontend Dockerfile
# =============================================================================
# Multi-stage build with optimized layers and caching
# =============================================================================

# ---- Stage 1: Builder ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies with better caching
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --no-fund && npm cache clean --force && npm install --save-dev esbuild

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

# Add cache headers for static assets
RUN echo '# Cache static assets for 1 year\n\
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {\n\
    expires 1y;\n\
    add_header Cache-Control "public, immutable";\n\
}\n\
\n# Compress responses\n\
gzip on;\n\
gzip_vary on;\n\
gzip_min_length 1024;\n\
gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml application/json;\n\
gzip_disable "MSIE [1-6]\\.";\n' > /etc/nginx/conf.d/cache.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]