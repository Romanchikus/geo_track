FROM node:22-alpine AS web

WORKDIR /app

COPY services/web/package.json services/web/package-lock.json ./
RUN npm ci
COPY services/web ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx/api.locations.conf /etc/nginx/api.locations.conf
COPY deploy/nginx/proxy-params.conf /etc/nginx/proxy-params.conf
COPY --from=web /app/dist /usr/share/nginx/html
