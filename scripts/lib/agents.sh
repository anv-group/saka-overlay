#!/bin/bash
# Agent module for ralph.sh
# Supported Docker Sandboxes agents and command construction.
#
# Sandbox naming + login command construction has a JS twin in
# `bin/lib/sandbox-name.js` used by the install CLI to precompute names
# at the end of `npx @pageai/ralph-loop`. Both implementations MUST
# produce byte-identical sandbox names for the same (agent, project)
# pair. See RALPH.md ("Keeping Bash and JavaScript in sync") and the
# parity test in `tests/test-sandbox-name-js.js`.

# Mirrored in bin/lib/sandbox-name.js (SUPPORTED_AGENTS).
SUPPORTED_AGENTS="antigravity claude codex copilot cursor gemini opencode"

# Print the supported agent list for help and validation messages.
supported_agents_list() {
  echo "$SUPPORTED_AGENTS"
}

# Normalize user-provided agent names for case-insensitive matching.
normalize_agent_name() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

# Return success when the agent slug is one Ralph knows how to run.
is_supported_agent() {
  case "$1" in
    antigravity|claude|codex|copilot|cursor|gemini|opencode)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Human-friendly agent name for status and error messages.
agent_display_name() {
  case "$1" in
    antigravity) echo "Antigravity" ;;
    claude) echo "Claude" ;;
    codex) echo "Codex" ;;
    copilot) echo "Copilot" ;;
    cursor) echo "Cursor" ;;
    gemini) echo "Gemini" ;;
    opencode) echo "OpenCode" ;;
    *) echo "$1" ;;
  esac
}

# Claude's stream-json output is currently the only fully parsed output path.
agent_uses_stream_json() {
  [ "$1" = "claude" ]
}

# Authentication command users can run before starting Ralph.
# Mirrored in bin/lib/sandbox-name.js (agentLoginCommand).
#
# Callers pass `exists` (1/0); see `sbx_run_command` for how it picks
# between the create and attach forms.
agent_login_command() {
  sbx_run_command "${1:-claude}" "${2:-}" "${3:-0}"
}

# Print the sbx client version as MAJOR.MINOR, or nothing when unknown.
# Prefers the "Client Version" line and falls back to the first number that
# follows the word "version"; anything else counts as unknown. `sbx version` is given 5 seconds, since it also
# contacts the daemon and must never hang Ralph's startup.
sbx_client_version() {
  local out_file
  out_file=$(mktemp)
  sbx version > "$out_file" 2>/dev/null &
  local pid=$!
  ( sleep 5; kill "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local watchdog=$!
  wait "$pid" 2>/dev/null || true
  kill "$watchdog" 2>/dev/null || true
  wait "$watchdog" 2>/dev/null || true

  local lower version
  lower=$(tr '[:upper:]' '[:lower:]' < "$out_file")
  rm -f "$out_file"
  version=$(printf '%s\n' "$lower" \
    | sed -n 's/^.*client version[^0-9]*v\{0,1\}\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/p' | head -1)
  if [ -z "$version" ]; then
    version=$(printf '%s\n' "$lower" \
      | sed -n 's/^.*version[^0-9]*v\{0,1\}\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/p' | head -1)
  fi
  case "$version" in
    [0-9]*.[0-9]*) echo "$version" ;;
  esac
}

# Return success when the installed sbx re-attaches with `sbx run --name`.
# sbx v0.33.0 made `--name` work for existing sandboxes and deprecated
# `sbx run <name>`; older releases reject `--name` on an existing sandbox.
# Unknown versions keep the positional form, which every release accepts.
# The answer is cached in SBX_NAMED_ATTACH for the life of the shell.
sbx_supports_named_attach() {
  if [ "${SBX_NAMED_ATTACH:-}" != "0" ] && [ "${SBX_NAMED_ATTACH:-}" != "1" ]; then
    local version
    version=$(sbx_client_version)
    SBX_NAMED_ATTACH=0
    if [ -n "$version" ]; then
      local major="${version%%.*}"
      local minor="${version#*.}"
      if [ "$major" -gt 0 ] || [ "$minor" -ge 33 ]; then
        SBX_NAMED_ATTACH=1
      fi
    fi
  fi
  [ "$SBX_NAMED_ATTACH" = "1" ]
}

# Build the `sbx run` prefix for an agent sandbox.
# Create form: `sbx run --name <name> <agent> .`. For an existing sandbox,
# sbx >= 0.33 re-enters with the same create form, while older sbx needs
# the positional attach form `sbx run <name>`.
# Usage: sbx_run_command <agent> [sandbox_name] [exists]
sbx_run_command() {
  local agent="${1:-claude}"
  local sandbox_name="${2:-}"
  local exists="${3:-0}"

  if [ -z "$sandbox_name" ]; then
    echo "sbx run $agent ."
  elif [ "$exists" = "1" ] && ! sbx_supports_named_attach; then
    echo "sbx run $sandbox_name"
  else
    echo "sbx run --name $sandbox_name $agent ."
  fi
}

# sbx ports command for publishing a HOST:SANDBOX mapping on a given sandbox.
# Targets a name regardless of lifecycle, so the string is the same for
# create/attach. Callers must ensure the sandbox exists before suggesting
# this command (sbx ports requires a running sandbox).
agent_ports_command() {
  local sandbox_name="${1:-}"
  local ports="${2:-3000:3000}"
  echo "sbx ports $sandbox_name --publish $ports"
}

# Snapshot the names sbx currently knows about, one per line, so callers
# can branch each agent's suggestion between create and attach without
# spawning N subprocesses. Returns empty string when sbx is missing or
# errors (callers treat empty as "nothing exists yet").
list_existing_sandboxes() {
  if ! command -v sbx >/dev/null 2>&1; then
    return 0
  fi
  sbx ls --quiet 2>/dev/null || true
}

# Test whether $1 appears as a line in $2 (the snapshot).
sandbox_in_snapshot() {
  local name="$1"
  local snapshot="$2"
  [ -n "$name" ] || return 1
  [ -n "$snapshot" ] || return 1
  printf '%s\n' "$snapshot" | grep -Fxq -- "$name"
}

# Print sbx ports command for every supported agent's sandbox.
print_ports_suggestions() {
  local selected_agent="${1:-claude}"
  local project_path="${2:-$PWD}"
  local ports="${3:-3000:3000}"
  local agent
  local sandbox_name
  local command
  local label
  local snapshot
  local exists

  snapshot=$(list_existing_sandboxes)

  echo -e "  ${Y}Port-publish commands for this project:${R}"
  for agent in $(supported_agents_list); do
    sandbox_name=$(build_sandbox_name "$agent" "$project_path")
    label="$(agent_display_name "$agent")"

    if sandbox_in_snapshot "$sandbox_name" "$snapshot"; then
      exists=1
    else
      exists=0
    fi

    if [ "$exists" = "1" ]; then
      command=$(agent_ports_command "$sandbox_name" "$ports")
      if [ "$agent" = "$selected_agent" ]; then
        echo -e "  ${GR}→ ${label}:${R} ${C}${command}${R}"
      else
        echo -e "    ${label}: ${D}${command}${R}"
      fi
    else
      # sbx ports requires the sandbox to exist; show the user how to
      # create it first instead of printing a command that would error.
      command=$(agent_login_command "$agent" "$sandbox_name" 0)
      if [ "$agent" = "$selected_agent" ]; then
        echo -e "  ${GR}→ ${label}:${R} ${D}(create the sandbox first: ${command})${R}"
      else
        echo -e "    ${label}: ${D}(create the sandbox first: ${command})${R}"
      fi
    fi
  done
}

# Print every supported agent login command for this project.
print_login_suggestions() {
  local selected_agent="${1:-claude}"
  local project_path="${2:-$PWD}"
  local agent
  local sandbox_name
  local command
  local label
  local snapshot
  local exists

  snapshot=$(list_existing_sandboxes)
  sbx_supports_named_attach || true

  echo -e "  ${Y}Login commands for this project:${R}"
  for agent in $(supported_agents_list); do
    sandbox_name=$(build_sandbox_name "$agent" "$project_path")
    label="$(agent_display_name "$agent")"

    if sandbox_in_snapshot "$sandbox_name" "$snapshot"; then
      exists=1
    else
      exists=0
    fi

    command=$(agent_login_command "$agent" "$sandbox_name" "$exists")

    if [ "$agent" = "$selected_agent" ]; then
      echo -e "  ${GR}→ ${label}:${R} ${C}${command}${R}"
    else
      echo -e "    ${label}: ${D}${command}${R}"
    fi
  done
}

# Authentication failure patterns seen across supported agent CLIs.
agent_auth_error_patterns() {
  case "$1" in
    antigravity)
      echo "not authenticated|authentication required|Unauthorized|Invalid API key|login required"
      ;;
    claude)
      echo "Invalid API key|Please run /login|not authenticated|authentication required"
      ;;
    codex)
      echo "codex login|not authenticated|authentication required|Unauthorized|Invalid API key"
      ;;
    copilot)
      echo "gh auth login|not authenticated|authentication required|Unauthorized"
      ;;
    cursor)
      echo "cursor login|not authenticated|authentication required|Unauthorized|Invalid API key"
      ;;
    gemini)
      echo "gemini auth|not authenticated|authentication required|API key not valid|Invalid API key"
      ;;
    opencode)
      echo "opencode auth login|not authenticated|authentication required|Unauthorized|Invalid API key"
      ;;
    *)
      echo "Invalid API key|not authenticated|authentication required|Unauthorized"
      ;;
  esac
}

# Convert project and agent values into Docker Sandboxes-safe name segments.
# Mirrored in bin/lib/sandbox-name.js (sanitizeSandboxNameSegment).
sanitize_sandbox_name_segment() {
  local value="${1:-sandbox}"

  value=$(printf "%s" "$value" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')

  if [ -z "$value" ]; then
    value="sandbox"
  fi

  printf "%s" "$value"
}

# Return an 8-character deterministic hash for an absolute project path.
# Mirrored in bin/lib/sandbox-name.js (sandboxPathHash). The JS side
# uses Node's crypto.createHash('sha256'); this side prefers `shasum`,
# falls back to `sha256sum`, and finally to `cksum` (which would NOT
# match the JS output, so prefer environments where shasum/sha256sum
# is available).
sandbox_path_hash() {
  local project_path="$1"

  if command -v shasum >/dev/null 2>&1; then
    printf "%s" "$project_path" | shasum -a 256 | awk '{print substr($1, 1, 8)}'
  elif command -v sha256sum >/dev/null 2>&1; then
    printf "%s" "$project_path" | sha256sum | awk '{print substr($1, 1, 8)}'
  else
    printf "%s" "$project_path" | cksum | awk '{printf "%08x", $1}'
  fi
}

# Build Ralph's deterministic Docker Sandboxes name for this project and agent.
# Mirrored in bin/lib/sandbox-name.js (buildSandboxName).
build_sandbox_name() {
  local agent="${1:-claude}"
  local project_path="${2:-$PWD}"
  local safe_agent
  local safe_project
  local hash

  safe_agent=$(sanitize_sandbox_name_segment "$agent")
  safe_project=$(sanitize_sandbox_name_segment "$(basename "$project_path")")
  hash=$(sandbox_path_hash "$project_path")

  printf "ralph-%s-%s-%s" "$safe_agent" "$safe_project" "$hash"
}

# Probe whether a named sandbox already exists. Returns 0 (exists) only on
# an exact match in `sbx ls --quiet`. Returns 1 on missing name, missing
# sbx, transient `sbx ls` failure, or no match — callers in that case
# should fall through to the create form so the real `sbx run` error
# surfaces if anything is genuinely broken.
sandbox_exists() {
  local name="$1"
  [ -n "$name" ] || return 1
  command -v sbx >/dev/null 2>&1 || return 1
  sbx ls --quiet 2>/dev/null | grep -Fxq -- "$name"
}

# Shell-quote any extra args passed after Ralph's own -- separator.
format_agent_extra_args() {
  local output=""
  local arg
  local quoted

  for arg in "${AGENT_EXTRA_ARGS[@]}"; do
    printf -v quoted "%q" "$arg"
    output="$output $quoted"
  done

  printf "%s" "$output"
}

# Build the command executed inside script(1)'s pseudo-TTY.
#
# `exists` (3rd arg, default 0) is passed to `sbx_run_command`. Every form
# accepts the same `[-- AGENT_ARGS...]` tail, so the per-agent printf lines
# below stay identical.
build_agent_command() {
  local agent="${1:-claude}"
  local sandbox_name="${2:-}"
  local exists="${3:-0}"
  local extra_args
  local sbx_run
  extra_args=$(format_agent_extra_args)

  if [ "$agent" = "antigravity" ]; then
    printf 'agy --dangerously-skip-permissions --mode auto%s -p "$PROMPT_CONTENT"' "$extra_args"
    return 0
  fi

  sbx_run=$(sbx_run_command "$agent" "$sandbox_name" "$exists")

  case "$agent" in
    claude)
      printf '%s -- --output-format stream-json --verbose%s -p "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    codex)
      printf '%s -- exec%s "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    copilot)
      printf '%s --%s -p "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    cursor)
      printf '%s -- -p%s "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    gemini)
      printf '%s --%s -p "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    opencode)
      printf '%s -- run%s "$PROMPT_CONTENT"' "$sbx_run" "$extra_args"
      ;;
    *)
      return 1
      ;;
  esac
}
