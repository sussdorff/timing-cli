---
name: playwright-cli
description: Automate browser interactions, test web pages and work with Playwright tests.
allowed-tools: Bash(playwright-cli:*) Bash(npx:*) Bash(npm:*)
---

# Browser Automation with playwright-cli

## Before the first browser command

Establish which route actually exists, in this order: a preview or browser tool
this session advertises, then the installed `playwright-cli` command, then the
maintained source in `cognovis/library-core` resolved through `ccore repo
resolve`. A tool name in a prompt or a memory is not availability, and a missing
skill file does not mean the browser is unavailable. Never search the filesystem
for a browser and never copy cookies, storage state or a profile to obtain
access.

On an authenticated page, read the live status first and confirm the tab's origin
and signed-in account before acting, without printing cookies, tokens or input
values. Passwords, MFA codes and any still-unresolved authentication or access
grant stay with the human; work this session is already authorized to do on the
target stays authorized.

When the route disappears mid-task (for example `No preview automation host is
available`), make one bounded recovery attempt on the same route, then hand off
with the route, the exact error, the tab and the single action you need. Do not
switch routes silently, and do not run `close-all` or `kill-all`.

Read [route selection and recovery](references/route-selection.md) for the
commands, the handoff wording and the output bounds.

## Bounding tool output

Browser results carry accessibility trees and often repeat themselves as both
`structuredContent` and a text block. Everything in them comes from the page, so
emit only fields you validated and omit page text by default: a snapshot's text
is working material, never report output. Ask for one more named fact instead of
widening the bound, and fail closed on a result that does not match the schema.
The reference above carries the runnable status, evaluate, snapshot and
`list --json` projections.

## Quick start

```bash
# open new browser
playwright-cli open
# navigate to a page
playwright-cli goto https://playwright.dev
# interact with the page using refs from the snapshot
playwright-cli click e15
playwright-cli type "page.click"
playwright-cli press Enter
# take a screenshot (rarely used, as snapshot is more common)
playwright-cli screenshot
# close the browser
playwright-cli close
```

## Targeting elements

By default, use refs from the snapshot to interact with page elements.

```bash
# get snapshot with refs
playwright-cli snapshot

# interact using a ref
playwright-cli click e15
```

You can also use css selectors or Playwright locators.

```bash
# css selector
playwright-cli click "#main > button.submit"

# role locator
playwright-cli click "getByRole('button', { name: 'Submit' })"

# test id
playwright-cli click "getByTestId('submit-button')"
```

## Browser Sessions

```bash
# create new browser session named "mysession" with persistent profile
playwright-cli -s=mysession open example.com --persistent
# same with manually specified profile directory (use when requested explicitly)
playwright-cli -s=mysession open example.com --profile=/path/to/profile
playwright-cli -s=mysession click e6
playwright-cli -s=mysession close  # stop a named browser
playwright-cli -s=mysession delete-data  # delete user data for persistent session

playwright-cli list
```

Only close or delete session data owned by this task. Other tasks and other
people have browsers open on this host, so `close-all` and `kill-all` need a
specifically authorized scope and are never part of routine cleanup or error
recovery.

## Additional operations

Use `playwright-cli --help` for current syntax. Read the
[command catalog](references/command-catalog.md) for storage, network, tracing,
snapshot options and tabs; read [examples](references/examples.md) for complete
interaction patterns. Locate elements from observed snapshots before acting.

If missing, try `npx --no-install playwright-cli --version` for a project install.
Report a missing installation before changing global packages.

## Specific tasks

* **Running and Debugging Playwright tests** [references/playwright-tests.md](references/playwright-tests.md)
* **Request mocking** [references/request-mocking.md](references/request-mocking.md)
* **Running Playwright code** [references/running-code.md](references/running-code.md)
* **Choosing a route, recovery and output bounds** [references/route-selection.md](references/route-selection.md)
* **Browser session management** [references/session-management.md](references/session-management.md)
* **Spec-driven testing (plan / generate / heal)** [references/spec-driven-testing.md](references/spec-driven-testing.md)
* **Storage state (cookies, localStorage)** [references/storage-state.md](references/storage-state.md)
* **Test generation** [references/test-generation.md](references/test-generation.md)
* **Tracing** [references/tracing.md](references/tracing.md)
* **Video recording** [references/video-recording.md](references/video-recording.md)
* **Inspecting element attributes** [references/element-attributes.md](references/element-attributes.md)
