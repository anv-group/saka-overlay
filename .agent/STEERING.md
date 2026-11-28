# **Critical Steering Work**

## Ensure the sandbox is running correctly

This sandbox runs emulated aarch64 Linux. Apply as needed:

- **Node >= 22 (always; agent-browser requires it):** Install nvm, persist to `/etc/sandbox-persistent.sh` with `unset NPM_CONFIG_PREFIX` before the nvm source line. Never add bash_completion to that file. Never use `sudo npm i -g`. Then symlink Node into `/usr/local/bin`, because Claude Code hooks run `node` via plain `/bin/sh` with Claude's startup PATH, which never loads nvm (re-run this after changing the nvm default version):
  ```
  . /etc/sandbox-persistent.sh && nvm use --silent default
  for bin in node npm npx; do
    p="$(nvm which default | sed "s#/node\$#/$bin#")"
    [ -x "$p" ] && sudo ln -sf "$p" "/usr/local/bin/$bin" || echo "FAILED to link $bin ($p)"
  done
  env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin sh -c 'node -v && npm -v && npx -v'   # must print three versions
  ```

- **Native binary SIGILL crashes (npm):** `npm install` will produce broken arm64 binaries. Follow this exact sequence:

  1. Run `npm install --ignore-scripts` (prevents SIGILL during install)
  2. Fix **all** known native binaries — for each package below, run:
     ```
     cd /tmp && npm pack <pkg>@<version> && tar xzf <tarball> && cp package/<binary> <node_modules_path> && rm -rf package
     ```
     Known SIGILL packages (check versions in node_modules):
     - `@esbuild/linux-arm64` → `bin/esbuild`
     - `@rollup/rollup-linux-arm64-gnu` → `rollup.linux-arm64-gnu.node`
     - `@tailwindcss/oxide-linux-arm64-gnu` → `tailwindcss-oxide.linux-arm64-gnu.node`
     - `@unrs/resolver-binding-linux-arm64-gnu` → `resolver.linux-arm64-gnu.node`
     - `lightningcss-linux-arm64-gnu` → `lightningcss.linux-arm64-gnu.node`
  3. **Verify each binary** before proceeding: `node -e "require('<pkg>')"` (for esbuild, use `node_modules/@esbuild/linux-arm64/bin/esbuild --version` instead since it's a standalone binary, not a requireable module)
  4. **Scan for corrupted files** — `--ignore-scripts` can produce JS files with null bytes:
     ```
     find node_modules -name '*.js' -size +50k | while read f; do
       if od -c "$f" | grep -q '\\0'; then echo "CORRUPT: $f"; fi
     done
     ```
     Fix: `rm -rf node_modules/<corrupt-pkg> && npm install --ignore-scripts`
     Re-scan until clean. Only then start the dev server.

## Main Tasks

Install dependencies (using the sequence above), then install Playwright system dependencies: `sudo npx playwright install-deps chromium 2>&1`. Allow up to 10 minutes for tasks to complete.

Then install the Playwright browser: `npx playwright install chromium`

Point agent-browser at Playwright's Chromium (agent-browser's own Chrome download has no Linux ARM64 build). Persist it:

```
echo "export AGENT_BROWSER_EXECUTABLE_PATH=\"$(ls -d /home/agent/.cache/ms-playwright/chromium-*/chrome-linux/chrome | sort -V | tail -1)\"" | sudo tee -a /etc/sandbox-persistent.sh
source /etc/sandbox-persistent.sh
```

Then install agent-browser: `npm i -g agent-browser && agent-browser install --with-deps`. This is for its system libraries only; its browser download may fail, which is fine once the executable path is set.

Start the dev server, then verify: `agent-browser open http://localhost:3000`, check `agent-browser errors` and `agent-browser console` are clean, and save a screenshot to `.agent/screenshots/` with `agent-browser screenshot .agent/screenshots/steering.png`. If agent-browser and Playwright both cannot open the dev server for environmental reasons, exit with `<promise>BLOCKED:cannot smoke test</promise>`.

---

After you finish this work, exit with message `Steering complete` and clear this file with the mention "_No critical work to do_"
