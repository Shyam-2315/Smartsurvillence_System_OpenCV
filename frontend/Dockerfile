FROM node:22-slim

WORKDIR /app

COPY frontend/package*.json /app/
COPY frontend/bun.lock /app/bun.lock

RUN npm install

COPY frontend/ /app/

EXPOSE 3000

# TanStack Start: build then serve preview
CMD ["sh", "-c", "npm run build && ln -sf index.js dist/server/server.js && npm run preview -- --host 0.0.0.0 --port 3000"]
