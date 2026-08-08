FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
COPY sdk/typescript ./sdk/typescript
COPY packages/ui-svelte ./packages/ui-svelte
COPY apps/web ./apps/web
COPY package.json ./package.json
RUN npm install --workspace=ccc-glass --workspace=@ultradex/sdk --workspace=@ravenhelm/ui-svelte
RUN npm run build --workspace=@ultradex/sdk
RUN npm run build --workspace=ccc-glass

FROM nginx:1.27-alpine
COPY apps/web/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/build /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK CMD wget -qO- http://127.0.0.1:8080/ || exit 1
