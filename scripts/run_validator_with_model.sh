#!/bin/bash
# Run the validator with a real Ollama model invocation (adjust model name as needed)
cd "$(dirname "$0")/.."
export LOG_FILE=./validate_moodle_pilot_test.log
# Create a minimal test Moodle workspace so validator doesn't fail early
TEST_MOODLE_DIR="$(pwd)/test_moodle"
mkdir -p "$TEST_MOODLE_DIR/dataroot"
cat > "$TEST_MOODLE_DIR/config.php" <<'PHP'
<?php
$CFG = new stdClass();
$CFG->dataroot = "'
PHP
export MOODLE_PATH="$TEST_MOODLE_DIR"
export MODEL_CMD='ollama run qwen3:1.7b "Respond ONLY with JSON matching {\"author\":\"string\",\"bio\":\"string\"}. Provide an object with keys author and bio."'
export MODEL_REPAIR_TEMPLATE='ollama run qwen3:1.7b "Fix output: {error}. Original: {output}. Respond ONLY with valid JSON."'
export MODEL_TIMEOUT=120

bash validate_moodle_pilot.sh
