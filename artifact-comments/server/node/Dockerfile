# artifact-comments self-hosted server.
# Build from the repository root, so the client script is in the image:
#
#   docker build -f server/node/Dockerfile -t artifact-comments .
#   docker run -p 8787:8787 -v ac-data:/data \
#     -e ARTIFACT_COMMENTS_TOKEN=change-me \
#     -e ALLOWED_ORIGINS=https://docs.example.com \
#     artifact-comments
#
# Mount a folder of pages at /site and add "--static /site" to serve them too.
FROM node:22-alpine

WORKDIR /app
COPY client/artifact-comments.js client/artifact-comments.js
COPY server/node/server.mjs server/node/package.json server/node/

RUN mkdir -p /data && chown node:node /data
USER node
VOLUME /data
EXPOSE 8787

ENTRYPOINT ["node", "--no-warnings=ExperimentalWarning", "server/node/server.mjs", "--host", "0.0.0.0", "--port", "8787", "--db", "/data/comments.db"]
