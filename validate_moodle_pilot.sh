#!/usr/bin/env bash
set -euo pipefail

# Validator that uses the helper utilities in validate_moodle_pilot_helpers.sh
# Creates a concise exit summary and non-zero exit on failure.

# Logging / rotation settings
LOG_FILE="${LOG_FILE:-/var/log/validate_moodle_pilot.log}"
# Max size in bytes before rotating (5 MiB)
MAX_LOG_SIZE=${MAX_LOG_SIZE:-5242880}
# Number of rotated files to keep (configurable via env or .validate_moodle_pilot.env)
# Example: export MAX_ROTATED_FILES=10
MAX_ROTATED_FILES=${MAX_ROTATED_FILES:-7}
# Max total size for all rotated logs (bytes). When exceeded, oldest files are removed.
MAX_TOTAL_LOG_SIZE=${MAX_TOTAL_LOG_SIZE:-52428800}
# Max age for rotated logs in days. Files older than this will be removed.
MAX_LOG_AGE_DAYS=${MAX_LOG_AGE_DAYS:-30}

# Optional env file in the same directory as this script. Allows callers (including
# sudo runs) to set defaults without editing the script. Example file contents:
#   MAX_ROTATED_FILES=10
#   MAX_LOG_SIZE=10485760
ENV_FILE="$(dirname "${BASH_SOURCE[0]}")/.validate_moodle_pilot.env"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
# Workspace copy path (Windows-accessible)
WORKSPACE_LOG_COPY="/mnt/c/Users/rod63/.continue/logs/validate_moodle_pilot.log"

# Capture wrapper: when first invoked, re-exec the script, capture stdout/stderr,
# then append the run output to the central log with a timestamp header and optionally
# rotate if the log grows too large. This keeps the main script body unchanged.
if [ -z "${__VMPP_CAPTURE:-}" ]; then
  TMPFILE=$(mktemp)
  export __VMPP_CAPTURE=1
  # Run the script body and capture everything
  bash "$0" "$@" >"$TMPFILE" 2>&1 || rc=$?

  # Rotate if large
  if [ -f "$LOG_FILE" ]; then
    if [ $(stat -c%s "$LOG_FILE") -gt "$MAX_LOG_SIZE" ]; then
      rotated_name="${LOG_FILE}.$(date +%s)"
      mv "$LOG_FILE" "$rotated_name"
      # remove older rotated logs beyond MAX_ROTATED_FILES
      if [ -n "${MAX_ROTATED_FILES:-}" ] && [ "$MAX_ROTATED_FILES" -gt 0 ]; then
        rotated_pattern="${LOG_FILE}.*"
        mapfile -t _oldfiles < <(ls -1t $rotated_pattern 2>/dev/null || true)
        if [ ${#_oldfiles[@]} -gt "$MAX_ROTATED_FILES" ]; then
          for ((i=MAX_ROTATED_FILES; i<${#_oldfiles[@]}; i++)); do
            f="${_oldfiles[$i]}"
            [ -n "$f" ] && sudo rm -f -- "$f" || true
          done
        fi
        unset _oldfiles
      fi

      # Remove rotated logs older than MAX_LOG_AGE_DAYS
      rotated_dir="$(dirname "$LOG_FILE")"
      rotated_base="$(basename "$LOG_FILE")"
      if [ -n "${MAX_LOG_AGE_DAYS:-}" ] && [ "$MAX_LOG_AGE_DAYS" -gt 0 ]; then
        find "$rotated_dir" -maxdepth 1 -type f -name "$rotated_base.*" -mtime +"$MAX_LOG_AGE_DAYS" -print0 | xargs -0 sudo rm -f -- 2>/dev/null || true
      fi

      # Enforce max total size for rotated logs: delete oldest until under limit
      if [ -n "${MAX_TOTAL_LOG_SIZE:-}" ] && [ "$MAX_TOTAL_LOG_SIZE" -gt 0 ]; then
        # loop removing oldest rotated file until total size <= MAX_TOTAL_LOG_SIZE
        while :; do
          total=$(find "$rotated_dir" -maxdepth 1 -type f -name "$rotated_base.*" -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {print s+0}')
          total=${total:-0}
          if [ "$total" -le "$MAX_TOTAL_LOG_SIZE" ]; then
            break
          fi
          oldest=$(find "$rotated_dir" -maxdepth 1 -type f -name "$rotated_base.*" -printf '%T@ %p\n' 2>/dev/null | sort -n | head -n1 | cut -d' ' -f2-)
          if [ -z "$oldest" ]; then
            break
          fi
          sudo rm -f -- "$oldest" 2>/dev/null || break
        done
      fi
    fi
  fi

  # Determine whether sudo is usable without password; fall back to no-sudo if not
  SUDO_CMD=""
  if sudo -n true 2>/dev/null; then
    SUDO_CMD="sudo"
  fi
  # Append header and captured output
  printf '\n[%s] === Validator run: %s ===\n' "$(date '+%F %T')" "$*" | $SUDO_CMD tee -a "$LOG_FILE" >/dev/null
  $SUDO_CMD tee -a "$LOG_FILE" <"$TMPFILE" >/dev/null

  # Copy a workspace-accessible current log (non-fatal)
  if mkdir -p "$(dirname "$WORKSPACE_LOG_COPY")" 2>/dev/null; then
  $SUDO_CMD cp "$LOG_FILE" "$WORKSPACE_LOG_COPY" 2>/dev/null || true
  # try to set ownership so the Windows user can access it
  $SUDO_CMD chown $(id -u):$(id -g) "$WORKSPACE_LOG_COPY" 2>/dev/null || true
    # Create a timestamped copy for uploads to avoid overwrites
    TS="$(date +%Y%m%d_%H%M%S)"
    TIMESTAMPED_WORKSPACE_COPY="$(dirname "$WORKSPACE_LOG_COPY")/validate_moodle_${TS}.log"
    $SUDO_CMD cp "$LOG_FILE" "$TIMESTAMPED_WORKSPACE_COPY" 2>/dev/null || true
    $SUDO_CMD chown $(id -u):$(id -g) "$TIMESTAMPED_WORKSPACE_COPY" 2>/dev/null || true
    export TIMESTAMPED_WORKSPACE_COPY
  fi

  # Optional: upload the current log to a remote using rclone when configured.
  # Set RCLONE_REMOTE to a remote:path (e.g., s3:mybucket/path or remote:folder)
  if [ -n "${RCLONE_REMOTE:-}" ]; then
    # Try rclone first if available
    if command -v rclone >/dev/null 2>&1; then
      printf '[%s] %s\n' "$(date '+%F %T')" "Uploading log to remote: $RCLONE_REMOTE" | $SUDO_CMD tee -a "$LOG_FILE" >/dev/null

      # ensure remote path exists (create bucket/path if missing)
      if command -v rclone >/dev/null 2>&1 && [ -n "${RCLONE_REMOTE:-}" ]; then
        printf '[%s] %s\n' "$(date '+%F %T')" "Ensuring remote path exists: ${RCLONE_REMOTE%/}/validate-logs" | $SUDO_CMD tee -a "$LOG_FILE" >/dev/null
        rclone mkdir "${RCLONE_REMOTE%/}/validate-logs" ${RCLONE_ARGS:-} 2>&1 | $SUDO_CMD tee -a "$LOG_FILE" || true
      fi

      # choose timestamped workspace copy when available, else fall back to LOG_FILE
      SRC="${TIMESTAMPED_WORKSPACE_COPY:-$LOG_FILE}"
      DEST="${RCLONE_REMOTE%/}/validate-logs"
      if rclone copy "$SRC" "$DEST" ${RCLONE_ARGS:-} --progress 2>&1; then
        printf '[%s] %s\n' "$(date '+%F %T')" "rclone upload succeeded" | $SUDO_CMD tee -a "$LOG_FILE" >/dev/null
      else
        printf '[%s] %s\n' "$(date '+%F %T')" "rclone upload failed; attempting mc fallback" | sudo tee -a "$LOG_FILE" >/dev/null
        # mc fallback: prefer connecting via Docker network to the running minio container
        MINIO_USER="${MINIO_USER:-admin}"
        MINIO_PASS="${MINIO_PASS:-pass1234}"
        # prefer timestamped copy when available
        if [ -n "${TIMESTAMPED_WORKSPACE_COPY:-}" ]; then
          BASENAME_COPY="$(basename "$TIMESTAMPED_WORKSPACE_COPY")"
          DIRNAME_COPY="$(dirname "$TIMESTAMPED_WORKSPACE_COPY")"
        else
          BASENAME_COPY="$(basename "$WORKSPACE_LOG_COPY")"
          DIRNAME_COPY="$(dirname "$WORKSPACE_LOG_COPY")"
        fi
        if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^minio$'; then
          docker run --rm --network container:minio -v "$DIRNAME_COPY:/logs" minio/mc cp "/logs/$BASENAME_COPY" "http://$MINIO_USER:$MINIO_PASS@127.0.0.1:9000/moodle-validate-logs/validate-logs/" 2>&1 | sudo tee -a "$LOG_FILE" || true
        elif command -v docker >/dev/null 2>&1; then
          docker run --rm -v "$DIRNAME_COPY:/logs" minio/mc cp "/logs/$BASENAME_COPY" "http://$MINIO_USER:$MINIO_PASS@localhost:9000/moodle-validate-logs/validate-logs/" 2>&1 | sudo tee -a "$LOG_FILE" || true
        else
          printf '[%s] %s\n' "$(date '+%F %T')" "mc fallback not available (docker missing)" | sudo tee -a "$LOG_FILE" >/dev/null
        fi
      fi
    else
      printf '[%s] %s\n' "$(date '+%F %T')" "rclone not found; attempting mc fallback" | sudo tee -a "$LOG_FILE" >/dev/null
      MINIO_USER="${MINIO_USER:-admin}"
      MINIO_PASS="${MINIO_PASS:-pass1234}"
      if [ -n "${TIMESTAMPED_WORKSPACE_COPY:-}" ]; then
        BASENAME_COPY="$(basename "$TIMESTAMPED_WORKSPACE_COPY")"
        DIRNAME_COPY="$(dirname "$TIMESTAMPED_WORKSPACE_COPY")"
      else
        BASENAME_COPY="$(basename "$WORKSPACE_LOG_COPY")"
        DIRNAME_COPY="$(dirname "$WORKSPACE_LOG_COPY")"
      fi
      if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^minio$'; then
        docker run --rm --network container:minio -v "$DIRNAME_COPY:/logs" minio/mc cp "/logs/$BASENAME_COPY" "http://$MINIO_USER:$MINIO_PASS@127.0.0.1:9000/moodle-validate-logs/validate-logs/" 2>&1 | sudo tee -a "$LOG_FILE" || true
      elif command -v docker >/dev/null 2>&1; then
        docker run --rm -v "$DIRNAME_COPY:/logs" minio/mc cp "/logs/$BASENAME_COPY" "http://$MINIO_USER:$MINIO_PASS@localhost:9000/moodle-validate-logs/validate-logs/" 2>&1 | sudo tee -a "$LOG_FILE" || true
      else
        printf '[%s] %s\n' "$(date '+%F %T')" "mc fallback not available (docker missing)" | sudo tee -a "$LOG_FILE" >/dev/null
      fi
    fi
  fi

  rm -f "$TMPFILE"
  exit ${rc:-0}
fi

HELPERS_PATH="$(dirname "${BASH_SOURCE[0]}")/validate_moodle_pilot_helpers.sh"
if [ ! -f "$HELPERS_PATH" ]; then
  echo "Helpers file not found: $HELPERS_PATH" >&2
  exit 2
fi
source "$HELPERS_PATH"

# Track runtime for observability
START_TIME=$(date +%s)

usage() {
  cat <<EOF
Usage: $(basename "$0") [MOODLE_PATH]
  MOODLE_PATH  Directory of the Moodle installation (default: /var/www/moodle)

This script performs environment, service and basic DB checks using the
helper functions in validate_moodle_pilot_helpers.sh.
EOF
}

MOODLE_PATH="${1:-${MOODLE_PATH:-/var/www/moodle}}"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ ! -d "$MOODLE_PATH" ]; then
  fail "Moodle path not found: $MOODLE_PATH"
fi

log "Validating Moodle environment at: $MOODLE_PATH"

# Ensure required commands are available
require_command php
require_command mysql
require_command redis-cli || log "redis-cli not found; Redis checks will be skipped"
# Ensure Python is available for optional model-output wrapper
PYTHON_CMD=""
if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python3
else
  log "python not found; model-output wrapper disabled"
fi

# Basic environment / PHP CLI checks
check_command_versions

# Check services
check_mysql_running || fail "MySQL/MariaDB is not running or reachable"
if command -v redis-cli >/dev/null 2>&1; then
  check_redis_running || fail "Redis not running or reachable"
else
  log "Skipping Redis checks; redis-cli not available"
fi

# Try to read Moodle config.php to get DB details
MOODLE_CONFIG="$MOODLE_PATH/config.php"
if [ ! -f "$MOODLE_CONFIG" ]; then
  fail "Moodle config.php not found at $MOODLE_CONFIG"
fi

# Shell-friendly parsing for DB name and prefix (best effort)
# Use awk to extract single-quoted values to avoid complex shell-quoting issues.
DB_NAME="$(awk -F"'" '/\$CFG->dbname/ {print $2; exit}' "$MOODLE_CONFIG" || true)"
DB_PREFIX="$(awk -F"'" '/\$CFG->prefix/ {print $2; exit}' "$MOODLE_CONFIG" || true)"
DB_USER="$(awk -F"'" '/\$CFG->dbuser/ {print $2; exit}' "$MOODLE_CONFIG" || true)"
DB_PASS="$(awk -F"'" '/\$CFG->dbpass/ {print $2; exit}' "$MOODLE_CONFIG" || true)"
DB_HOST="$(awk -F"'" '/\$CFG->dbhost/ {print $2; exit}' "$MOODLE_CONFIG" || true)"

# Export DB vars for helper functions
export DB_NAME DB_PREFIX DB_USER DB_PASS DB_HOST

# Path to the JSON validation wrapper. When present, use it to run model
# commands and ensure only valid JSON is returned to the caller.
WRAPPER_PATH="$(dirname "${BASH_SOURCE[0]}")/scripts/ollama_output_wrapper.py"

# run_model: run a shell command that produces model output through the
# wrapper. Usage: run_model "<shell-cmd>" [schema-file] [repair-cmd-template]
run_model() {
  local cmd="$1"; shift || true
  local schema_file="${1:-}"; shift || true
  local repair_template="${1:-}"

  if [ ! -f "$WRAPPER_PATH" ]; then
    # Wrapper missing -> run command directly
    eval "$cmd"
    return $?
  fi

  # Build python invocation; rely on the wrapper to print JSON on success.
  if [ -n "$PYTHON_CMD" ]; then
    local pycmd=("$PYTHON_CMD" "$WRAPPER_PATH" --cmd "$cmd")
  else
    # No python available: fall back to running the command directly
    eval "$cmd"
    return $?
  fi
  if [ -n "$schema_file" ]; then
    pycmd+=(--schema-file "$schema_file")
  fi
  if [ -n "$repair_template" ]; then
    pycmd+=(--repair-cmd "$repair_template")
  fi
  if [ -n "${MODEL_TIMEOUT:-}" ]; then
    pycmd+=(--timeout "${MODEL_TIMEOUT}")
  fi

  # Execute the wrapper and let it print the validated JSON (or exit non-zero).
  "${pycmd[@]}"
}

if [ -z "$DB_NAME" ]; then
  log "Could not auto-detect DB name from config.php — continuing with manual checks"
else
  log "Detected DB: $DB_NAME  (prefix: ${DB_PREFIX:-none})"
  if ! db_exists "$DB_NAME"; then
    fail "Database '$DB_NAME' does not exist or is not reachable"
  fi

  # Basic table sanity checks
  for t in course user role config; do
    if table_exists "$t"; then
      log "Table exists: ${DB_PREFIX}${t}"
    else
      fail "Missing expected table: ${DB_PREFIX}${t}"
    fi
  done

  # Check admin user existence (username 'admin' or id 2)
  if user_exists 'admin'; then
    log "Admin user (admin) found"
  else
    log "Admin user 'admin' not found; checking for any users with id=2"
    if mysql_query "SELECT id FROM ${DB_PREFIX}user WHERE id=2 LIMIT 1;" >/dev/null 2>&1; then
      log "Found user with id=2"
    else
      fail "No admin user found (username 'admin' or id=2)"
    fi
  fi
fi

# Check file/dir permissions for dataroot if available in config.php
DATAROOT="$(awk -F"'" '/\$CFG->dataroot/ {print $2; exit}' "$MOODLE_CONFIG" || true)"

if [ -n "$DATAROOT" ]; then
  if [ -d "$DATAROOT" ] && [ -r "$DATAROOT" ] && [ -w "$DATAROOT" ]; then
    log "dataroot OK: $DATAROOT (exists, readable, writable)"
  else
    fail "dataroot missing or incorrect permissions: $DATAROOT"
  fi
else
  log "dataroot not found in config.php; skipping dataroot checks"
fi

# Optional checks for cron and queued tasks
if command -v php >/dev/null 2>&1; then
  if php -v >/dev/null 2>&1; then
    log "PHP CLI available"
  fi
fi

log "All configured checks passed"
# If a model command is provided via MODEL_CMD, run it through the JSON wrapper.
if [ -n "${MODEL_CMD:-}" ]; then
  log "Running configured model command via wrapper"
  # Allow optional schema file and repair template to be supplied via env
  if run_model "${MODEL_CMD}" "${MODEL_SCHEMA:-}" "${MODEL_REPAIR_TEMPLATE:-}"; then
    log "Model invocation succeeded"
  else
    fail "Model invocation failed"
  fi
fi
echo
log "Validator finished successfully"
# Emit runtime duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log "Validator runtime: ${DURATION}s"
exit 0
