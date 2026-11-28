#!/bin/bash
# Spinner module for ralph.sh
# Animated spinner display with step tracking
# Dependencies: constants.sh, timing.sh, terminal.sh, output.sh (strip_ansi)

# Spinner characters
SPINNER='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
SPINNER_PID=""
CURRENT_STEP="Thinking"
# Set to 1 when stdout is not a TTY: the animated, cursor-controlled spinner
# is replaced by plain, change-only status lines so piped logs stay clean.
SPINNER_PLAIN=0

# Spinner function - runs in background, reads step from STEP_FILE
# Usage: start_spinner; do_work; stop_spinner
start_spinner() {
  echo "Thinking" > "$STEP_FILE"
  echo "" > "$PREVIEW_LINE_FILE"

  # Without a TTY (piped/redirected output) the in-place cursor tricks below
  # cannot redraw and instead stack garbage into the log. Degrade to a plain
  # status line that is only emitted when the step changes.
  if [ "$ANSI_SUPPORTED" != "true" ]; then
    SPINNER_PLAIN=1
    SPINNER_PID=""
    echo -e "  ${C}•${R} Thinking"
    return 0
  fi
  SPINNER_PLAIN=0

  (
    # Spinner chars as array for proper unicode handling
    local -a SPIN_CHARS=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    local i=0
    local spin_len=${#SPIN_CHARS[@]}
    local term_width
    term_width=$(tput cols 2>/dev/null || echo 80)
    case "$term_width" in ''|*[!0-9]*) term_width=80 ;; esac
    [ "$term_width" -lt 20 ] && term_width=20
    local preview_max=$((term_width - 6))  # Leave room for "    ▸ "
    local step_max=$((term_width - 4))     # Leave room for "  ⠋ "
    while true; do
      local step
      step=$(cat "$STEP_FILE" 2>/dev/null || echo "Thinking")
      local preview
      preview=$(cat "$PREVIEW_LINE_FILE" 2>/dev/null || echo "")
      local char="${SPIN_CHARS[$i]}"

      # Hard-truncate BOTH lines so neither can wrap onto a second physical
      # row. A wrapped line would throw off the cursor-up math below and make
      # the status stack instead of redrawing in place.
      if [ ${#step} -gt $step_max ]; then
        step="${step:0:$((step_max - 3))}..."
      fi
      if [ ${#preview} -gt $preview_max ]; then
        preview="${preview:0:$((preview_max - 3))}..."
      fi

      # Always render a fixed two-line region: line 1 = spinner + step,
      # line 2 = dim preview (or a cleared blank line). After drawing, the
      # cursor returns to the top of the region (\033[A), so the block height
      # is constant and lines can never accumulate.
      local line2=""
      if [ -n "$preview" ]; then
        printf -v line2 "    ${D}▸ %s${R}" "$preview"
      fi
      printf "\r\033[K  ${C}%s${R} %s\n\033[K%s\033[A" "$char" "$step" "$line2"

      i=$(( (i + 1) % spin_len ))
      sleep 0.1
    done
  ) &
  SPINNER_PID=$!
}

# Stop the spinner
stop_spinner() {
  # Plain (non-TTY) mode never started a background animation and printed no
  # cursor-control codes, so there is nothing to kill or clear.
  if [ "$SPINNER_PLAIN" = "1" ]; then
    SPINNER_PLAIN=0
    SPINNER_PID=""
    return 0
  fi
  if [ -n "$SPINNER_PID" ] && kill -0 "$SPINNER_PID" 2>/dev/null; then
    kill "$SPINNER_PID" 2>/dev/null
    wait "$SPINNER_PID" 2>/dev/null || true
    # Clear the two-line region (spinner + preview) and park cursor at top
    printf "\r\033[K\n\033[K\033[A\r"
  fi
  SPINNER_PID=""
}

# Update spinner step based on output line and record step timing
update_spinner_step() {
  local line="$1"
  local detected=$(detect_step "$line")
  if [ -n "$detected" ]; then
    # Clean step name (remove trailing spaces) for timing tracking
    local clean_step=$(echo "$detected" | LC_ALL=C sed 's/ *$//' 2>/dev/null)

    if [ "$SPINNER_PLAIN" = "1" ]; then
      # Non-TTY: emit a plain status line only when the step actually changes,
      # so logs get one line per phase instead of an animation flood.
      if [ "$clean_step" != "$CURRENT_STEP_NAME" ]; then
        echo -e "  ${C}•${R} $clean_step"
      fi
    else
      echo "$detected" > "$STEP_FILE"
    fi

    # Record timing if step changed (compare before record_step_time mutates
    # CURRENT_STEP_NAME). Runs in both TTY and plain modes.
    if [ "$clean_step" != "$CURRENT_STEP_NAME" ]; then
      record_step_time "$clean_step"
    fi
  fi
}

# Update the preview line shown under the spinner
update_preview_line() {
  # No live preview region exists in plain (non-TTY) mode.
  [ "$SPINNER_PLAIN" = "1" ] && return 0

  local line="$1"
  # Skip empty lines or lines that are just whitespace
  [ -z "$line" ] && return 0
  [[ "$line" =~ ^[[:space:]]*$ ]] && return 0

  # Strip ANSI/cursor-control escapes FIRST. Agents that aren't parsed as
  # stream-json (cursor, codex, etc.) feed their raw TUI output here, which
  # carries cursor-move/clear-line sequences. Left unstripped, those move the
  # real terminal cursor and corrupt the in-place spinner so status lines
  # stack endlessly.
  line=$(strip_ansi "$line")

  # Collapse any remaining newlines/tabs/CR to spaces and keep a single line,
  # so multi-line content can't break cursor positioning.
  line=$(echo "$line" | LC_ALL=C tr '\n\t\r' ' ' 2>/dev/null | LC_ALL=C sed 's/  */ /g; s/^ *//; s/ *$//' 2>/dev/null | head -1)
  # Skip if sanitization resulted in empty string
  [ -z "$line" ] && return 0
  # Write to preview file (spinner reads this)
  echo "$line" > "$PREVIEW_LINE_FILE"
}
