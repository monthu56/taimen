# Руководство guide/ как статический сайт за периметром (маршрут /guide/*).
# Сборка та же, что `make guide` и CI: mkdocs --strict, битая ссылка роняет образ.
#   docker build -t taimen/guide:local guide
FROM python:3.12-slim AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdocs build --strict

FROM caddy:2-alpine
COPY --from=build /src/site /srv
EXPOSE 8080
CMD ["caddy", "file-server", "--root", "/srv", "--listen", ":8080"]
