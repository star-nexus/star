#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  --set=arena_password="$ARENA_DB_PASSWORD" --set=auth_password="$AUTH_DB_PASSWORD" <<'SQL'
CREATE USER arena WITH PASSWORD :'arena_password';
CREATE USER keycloak WITH PASSWORD :'auth_password';
CREATE DATABASE arena OWNER arena;
CREATE DATABASE keycloak OWNER keycloak;
SQL
