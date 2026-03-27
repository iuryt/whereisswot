FROM ghcr.io/prefix-dev/pixi:0.41.4 AS build

WORKDIR /app
COPY pixi.lock pyproject.toml ./
RUN pixi install --locked

COPY . .

RUN pixi shell-hook -s bash > /shell-hook.sh

FROM ubuntu:24.04 AS production

RUN useradd -m -u 1000 -o user || true
USER 1000
WORKDIR /app

COPY --from=build /app /app
COPY --from=build /shell-hook.sh /shell-hook.sh

EXPOSE 7860

ENTRYPOINT ["/bin/bash", "-c", "source /shell-hook.sh && exec \"$@\"", "--"]
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:7860"]
