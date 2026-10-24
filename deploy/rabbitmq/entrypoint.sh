#!/bin/sh
set -eu

cp /etc/rabbitmq/certs/ca.pem /var/lib/rabbitmq/ca.pem
cp /etc/rabbitmq/certs/server.pem /var/lib/rabbitmq/server.pem
cp /etc/rabbitmq/certs/server.key /var/lib/rabbitmq/server.key

chmod 600 /var/lib/rabbitmq/server.key
chown rabbitmq:rabbitmq \
    /var/lib/rabbitmq/ca.pem \
    /var/lib/rabbitmq/server.pem \
    /var/lib/rabbitmq/server.key

docker-entrypoint.sh rabbitmq-server &
pid=$!

trap 'kill -TERM "$pid" 2>/dev/null || true; wait "$pid" || true' TERM INT

i=0
until su-exec rabbitmq rabbitmq-diagnostics -q check_running; do
    if ! kill -0 "$pid" 2>/dev/null; then
        wait "$pid" || true
        echo "RabbitMQ exited during startup" >&2
        exit 1
    fi

    i=$((i + 1))
    if [ "$i" -ge 90 ]; then
        echo "RabbitMQ application did not start within 90 seconds" >&2
        exit 1
    fi

    sleep 1
done

su-exec rabbitmq rabbitmqctl import_definitions \
    /etc/rabbitmq/definitions.json \
    --timeout 60

wait "$pid"