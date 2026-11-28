#!/bin/bash
# Promise tags module for ralph.sh
# Semantic signals for agent communication
# Dependencies: None
#
# Promise tags allow the AI agent to communicate status to the loop controller.
# The script detects these tags in the agent's output to determine next actions.
#
# Tag Format: <promise>TYPE:content</promise>
#
# Available Tags:
#   <promise>COMPLETE</promise>     - All tasks finished successfully
#   <promise>BLOCKED:reason</promise>  - Agent is blocked and needs human help
#   <promise>DECIDE:question</promise> - Agent needs human decision/clarification
#   <promise>TASK-1:DONE</promise> - Task completed during this iteration
#
# Examples:
#   <promise>COMPLETE</promise>
#   <promise>BLOCKED:Missing API credentials for external service</promise>
#   <promise>DECIDE:Should we use REST or GraphQL for the new endpoint?</promise>
#   <promise>TASK-1:DONE</promise>

# Regex patterns for promise tags
PROMISE_COMPLETE_PATTERN='<promise>COMPLETE</promise>'
PROMISE_BLOCKED_PATTERN='<promise>BLOCKED:[^<]*</promise>'
PROMISE_DECIDE_PATTERN='<promise>DECIDE:[^<]*</promise>'
PROMISE_TASK_DONE_PATTERN='<promise>TASK-[A-Za-z0-9._-]+:DONE</promise>'

# Agents quote these tags all the time without meaning them: PROMPT.md,
# STEERING.md and task specs contain them, and tool output (cat, grep,
# pgrep -af on the agent's own process) echoes them into the stream. So the
# control signal is read only from the end of the agent's final message,
# where PROMPT.md requires it ("Your response must END after the promise
# tag"). Use `signal_text` to get that slice before calling the has_* and
# extract_* helpers below.

# Lines of output that can carry a signal, newest last: blank lines,
# carriage returns and Markdown code fence lines (``` or ~~~, any length,
# with or without an info string) are dropped.
# Usage: final_signal_lines "$text" [count]
final_signal_lines() {
  local text="$1"
  local count="${2:-1}"
  printf '%s\n' "$text" \
    | tr -d '\r' \
    | awk 'NF && $0 !~ /^[[:space:]]*(```+|~~~+)[^`]*$/' \
    | tail -n "$count"
}

# Placeholder tags from PROMPT.md and the docs. A prompt echoed into the
# output ends with one of these, so they never count as a signal.
PROMISE_PLACEHOLDER_PATTERN='<promise>(BLOCKED:brief description|BLOCKED:reason|DECIDE:question \(Option A vs B\)|DECIDE:question|TASK-\{ID\}:DONE)</promise>'

# Print the promise tags that end a block of text, one per line.
# The anchor is the last line (mode "last") or the last line holding a tag
# (mode "tag"). The anchor's last tag must end its line (closing Markdown and
# punctuation aside): a tag mid-sentence, like the ones in PROMPT.md, is a
# quote. Only the last tag on the anchor line counts, plus every tag
# on directly preceding lines that hold nothing but tags, so an agent may
# end with "<promise>COMPLETE</promise>" and a TASK-DONE line in any order.
# Prints nothing when the anchor's last tag is a placeholder.
# Usage: trailing_tags "$lines" last|tag
trailing_tags() {
  local lines="$1"
  local mode="$2"
  # The pattern goes through ENVIRON: awk -v would strip its backslashes.
  printf '%s\n' "$lines" | RALPH_PROMISE_PLACEHOLDER="$PROMISE_PLACEHOLDER_PATTERN" awk -v mode="$mode" '
    function all_tags(s,   out) {
      out = ""
      while (match(s, /<promise>[^<]*<\/promise>/)) {
        out = out substr(s, RSTART, RLENGTH) "\n"
        s = substr(s, RSTART + RLENGTH)
      }
      return out
    }
    function last_tag(s,   tag) {
      tag = ""
      while (match(s, /<promise>[^<]*<\/promise>/)) {
        tag = substr(s, RSTART, RLENGTH)
        s = substr(s, RSTART + RLENGTH)
      }
      after_tag = s
      return tag
    }
    function tags_only(s,   rest) {
      if (s !~ /<promise>[^<]*<\/promise>/) return 0
      rest = s
      gsub(/<promise>[^<]*<\/promise>/, "", rest)
      gsub(/[[:space:]`*_>-]/, "", rest)
      return rest == ""
    }
    { line[NR] = $0 }
    END {
      anchor = 0
      if (mode == "last") {
        anchor = NR
      } else {
        for (i = NR; i > 0; i--) {
          if (line[i] ~ /<promise>[^<]*<\/promise>/) { anchor = i; break }
        }
      }
      if (anchor == 0) exit
      placeholder = ENVIRON["RALPH_PROMISE_PLACEHOLDER"]
      tag = last_tag(line[anchor])
      if (tag == "" || tag ~ placeholder) exit
      if (after_tag !~ /^[[:space:]`*_.!)]*$/) exit
      out = tag "\n"
      for (i = anchor - 1; i > 0 && tags_only(line[i]); i--) {
        out = all_tags(line[i]) out
      }
      printf "%s", out
    }' | grep -vE "$PROMISE_PLACEHOLDER_PATTERN" || true
}

# Text that decides an iteration's control signal (COMPLETE/BLOCKED/DECIDE).
# With a final result message (Claude stream-json), it is the tags that end
# that message: the agent writes it itself, so tags earlier in it are quotes.
# Without one, the tags ending the last tag-bearing line in the tail of the
# parsed output stand in. The tail is wide enough to skip a usage footer some
# agent CLIs print after the final message.
# Usage: text=$(signal_text "$output" "$final_summary")
signal_text() {
  local output="$1"
  local final_summary="$2"
  if [ -n "$final_summary" ]; then
    trailing_tags "$(final_signal_lines "$final_summary" 50)" last
  else
    trailing_tags "$(final_signal_lines "$output" 20)" tag
  fi
}

# Check if output contains a COMPLETE tag
# Usage: if has_complete_tag "$output"; then ...
has_complete_tag() {
  local output="$1"
  echo "$output" | grep -q "$PROMISE_COMPLETE_PATTERN"
}

# Check if output contains a BLOCKED tag
# Usage: if has_blocked_tag "$output"; then ...
has_blocked_tag() {
  local output="$1"
  echo "$output" | grep -qE "$PROMISE_BLOCKED_PATTERN"
}

# Check if output contains a DECIDE tag
# Usage: if has_decide_tag "$output"; then ...
has_decide_tag() {
  local output="$1"
  echo "$output" | grep -qE "$PROMISE_DECIDE_PATTERN"
}

# Extract the reason from a BLOCKED tag
# Usage: reason=$(extract_blocked_reason "$output")
# Returns: the reason string, or empty if no tag found
extract_blocked_reason() {
  local output="$1"
  local match=$(echo "$output" | grep -oE "$PROMISE_BLOCKED_PATTERN" | head -1)
  if [ -n "$match" ]; then
    # Extract content between BLOCKED: and </promise>
    echo "$match" | sed 's/<promise>BLOCKED://;s/<\/promise>//'
  fi
}

# Extract the question from a DECIDE tag
# Usage: question=$(extract_decide_question "$output")
# Returns: the question string, or empty if no tag found
extract_decide_question() {
  local output="$1"
  local match=$(echo "$output" | grep -oE "$PROMISE_DECIDE_PATTERN" | head -1)
  if [ -n "$match" ]; then
    # Extract content between DECIDE: and </promise>
    echo "$match" | sed 's/<promise>DECIDE://;s/<\/promise>//'
  fi
}

# Extract completed task IDs from TASK-DONE tags
# Usage: extract_completed_task_ids "$output"
# Returns: one task ID per line, de-duplicated in first-seen order
extract_completed_task_ids() {
  local output="$1"
  echo "$output" \
    | grep -oE "$PROMISE_TASK_DONE_PATTERN" \
    | sed 's/<promise>//;s/:DONE<\/promise>//' \
    | awk '!seen[$0]++'
}

# Format completed task IDs for compact display
# Usage: task_ids=$(format_completed_task_ids "$output")
# Returns: comma-separated task IDs, or empty if no task completion tags exist
format_completed_task_ids() {
  local output="$1"
  extract_completed_task_ids "$output" | awk '
    NF {
      printf "%s%s", separator, $0
      separator = ", "
    }
    END {
      if (separator != "") {
        printf "\n"
      }
    }
  '
}

# Check if output contains any help-needed tag (BLOCKED or DECIDE)
# Usage: if needs_help "$output"; then ...
needs_help() {
  local output="$1"
  has_blocked_tag "$output" || has_decide_tag "$output"
}
