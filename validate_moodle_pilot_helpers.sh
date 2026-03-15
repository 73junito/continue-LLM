#!/usr/bin/env bash
set -euo pipefail

# Helper utilities for validate_moodle_pilot.sh
# Source this file from your validator script:
#   source /path/to/validate_moodle_pilot_helpers.sh

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

# (Webhook alerting removed) The validator no longer sends external alerts.

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR: required command not found: $1"
    exit 1
  fi
}

fail() {
  log "ERROR: $*"
  exit 1
}

service_running() {
  # return 0 if system service is active
  systemctl is-active --quiet "$1" 2>/dev/null
}

process_running() {
  # check by pgrep pattern
  pgrep -f "$1" >/dev/null 2>&1
}

check_mysql_running() {
  if service_running mysql || service_running mysqld; then
    return 0
  fi
  process_running mysqld && return 0 || return 1
}

check_redis_running() {
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli ping 2>/dev/null | grep -q -i PONG; then
      return 0
    else
      return 1
    fi
  fi
  # fallback to systemd
  service_running redis || service_running redis-server
}

mysql_query() {
  # mysql_query "SQL"
  local sql="$1"
  local -a mysql_cmd
  mysql_cmd=(mysql -N -s)
  mysql_cmd+=( -h "${DB_HOST:-localhost}" )
  mysql_cmd+=( -u"${DB_USER:-root}" )
  if [ -n "${DB_PASS:-}" ]; then
    mysql_cmd+=( -p"${DB_PASS}" )
  fi
  mysql_cmd+=( "${DB_NAME:-moodle}" )
  "${mysql_cmd[@]}" -e "$sql"
}

db_exists() {
  local db="${1:-${DB_NAME:-moodle}}"
  local -a mysql_cmd
  mysql_cmd=(mysql -h "${DB_HOST:-localhost}" -u"${DB_USER:-root}" )
  if [ -n "${DB_PASS:-}" ]; then
    mysql_cmd+=( -p"${DB_PASS}" )
  fi
  if "${mysql_cmd[@]}" -e "USE \"${db}\";" 2>/dev/null; then
    return 0
  else
    return 1
  fi
}

table_exists() {
  local table="$1"
  local prefix="${DB_PREFIX:-mdl_}"
  mysql_query "SHOW TABLES LIKE '${prefix}${table}';" | grep -q .
}

user_exists() {
  local username="$1"
  local table
  table="${DB_PREFIX:-mdl_}user"
  local sql
  sql=$(printf "SELECT id FROM \`%s\` WHERE username='%s' LIMIT 1;" "$table" "$username")
  mysql_query "$sql" | grep -q .
}

check_command_versions() {
  # optional: print simple versions for key commands
  for cmd in php mysql redis-cli systemctl; do
    if command -v "$cmd" >/dev/null 2>&1; then
      printf '%-12s: %s\n' "$cmd" "$("$cmd" --version 2>/dev/null | head -n1 || true)"
    else
      printf '%-12s: not found\n' "$cmd"
    fi
  done
}

assert() {
  # assert <command...>
  if ! "$@"; then
    fail "Assertion failed: $*"
  fi
}

# Example combined environment check
check_environment() {
  require_command php
  require_command mysql
  log "Checking MySQL..."
  if check_mysql_running; then
    log "MySQL running"
  else
    fail "MySQL not running"
  fi

  log "Checking Redis..."
  if check_redis_running; then
    log "Redis running"
  else
    log "Redis not running (optional depending on your setup)"
  fi

  log "Checking DB exists: ${DB_NAME:-moodle}"
  if db_exists; then
    log "Database exists"
  else
    fail "Database ${DB_NAME:-moodle} not found"
  fi
}

export -f log require_command fail service_running process_running check_mysql_running check_redis_running \
  mysql_query db_exists table_exists user_exists check_command_versions assert check_environment
