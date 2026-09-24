# Contexte de construction : apps/web (voir infra/RAILWAY_STAGING.md). Les
# catalogues de textes sont déjà copiés dans src/i18n/ par `npm run i18n:sync`
# et suivis par git : rien à récupérer hors de ce dossier pour construire.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
