/brainstorming

> ⛔ **ONE TASK PER INVOCATION & AUTONOMOUS MODE**
> - Complete **ONE** unchecked (`- [ ]`) task from `@TODO.md`, verify with tests, update `TODO.md` to `- [x]`, commit, output `<promise>TASK-1:DONE</promise>` (or `<promise>COMPLETE</promise>` if all tasks are done), and **STOP immediately**.
> - **AUTONOMOUS BRAINSTORMING OVERRIDE:** This prompt runs inside an unattended Ralph Loop (`agy -p`). During `/brainstorming`, **NEVER** ask questions to the user, **NEVER** call `ask_question`, and **NEVER** pause for user confirmation. Whenever `/brainstorming` presents options, ambiguities, or a design/plan gate, **ALWAYS** automatically choose the **recommended option** (or the simplest, cleanest engineering default that matches `AGENTS.md`) and proceed immediately to implementation.

## Before Starting

1. Read `@AGENTS.md` to follow project architecture, rules, and conventions.
2. Check `@.agent/STEERING.md` for any critical steering notes.
3. Read `@TODO.md` and pick **only the first unchecked (`- [ ]`) task**.
   - If **no** `- [ ]` tasks remain in `TODO.md`, output `<promise>COMPLETE</promise>` and stop.

## Workflow (Brainstorming -> Implement -> Verify -> Commit)

1. **Brainstorming (Autonomous):**
   - Inspect the relevant files in the codebase for the selected `TODO.md` task.
   - Formulate a concise design and implementation plan, automatically selecting the **recommended option** for every decision without asking the user.
2. **Implement:**
   - Implement the task cleanly according to `AGENTS.md` and the chosen design.
   - Add or update unit tests covering the new/changed behavior when applicable.
3. **Verify:**
   - Run the relevant tests (e.g. `pytest` or `python -m unittest` / `test_accuracy.py`) and ensure all affected checks pass.
   - Fix any failures or regressions before proceeding.
4. **Update State & Log:**
   - Mark ONLY the completed task in `TODO.md` from `- [ ]` to `- [x]`.
   - Prepend a brief entry (date, task summary, test result) at the top of `@.agent/logs/LOG.md`.
5. **Commit:**
   - Stage your changes and commit using Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, etc.).
   - Do **NOT** run `git push` or modify remotes.

## Promise Tags (Final Line of Response)

- After completing **one** task (and unchecked `- [ ]` items still remain in `TODO.md`):
  `<promise>TASK-1:DONE</promise>`
- After completing the **final** unchecked task in `TODO.md` (0 `- [ ]` items remain):
  `<promise>COMPLETE</promise>`
- Only if blocked by an unrecoverable environment/credential issue:
  `<promise>BLOCKED:brief description</promise>`
- **NEVER** output `<promise>DECIDE:...</promise>` — always pick the recommended option yourself.
