# ReticulumNewsnet — Claude Context

> **Maintenance:** When you fix a non-obvious bug or discover a gotcha that isn't derivable from reading
> the code, add it to [Known Gotchas](#known-gotchas) before ending the session.

## What This Is

A Usenet-inspired P2P threaded discussion app running over the [Reticulum Network Stack](https://reticulum.network).
Full design spec: `docs/superpowers/specs/2026-03-20-platform-redesign-design.md`

**Architecture:** Python daemon (RNS + FastAPI) + compiled Svelte PWA served as static files from the same process.

```
newsnet_main.py          ← entry point
newsnet/                 ← core: node, sync, store, config, identity, peers, filters, wizard
api/                     ← FastAPI app, auth, websocket hub, route modules
frontend/src/            ← Svelte 5 + Vite (NOT SvelteKit), hash-based routing
frontend/dist/           ← compiled output, served by FastAPI (build before running)
```

## Running

```bash
# Start the server (opens browser automatically after 1.5s)
python newsnet_main.py

# After any frontend change
cd frontend && npm run build

# Tests (RNS-dependent tests auto-skip if RNS not configured)
pytest tests/

# Full RNS logging (suppressed by default)
NEWSNET_DEBUG=1 python newsnet_main.py
```

Config file lives at `~/.config/reticulum-newsnet/config.toml`.

## Known Gotchas

### RNS must start in the main thread
`RNS.Reticulum()` calls `signal.signal()`, which Python only allows from the main thread.
**Do not** call `node.start()` from `run_in_executor`, a thread pool, or after uvicorn's event loop
has started. It must be called synchronously in `_run_server()` before `uvicorn.run()`.
- **Where:** `newsnet_main.py → _run_server()`, `newsnet/node.py → start()`
- **Symptom:** `ValueError: signal only works in main thread of the main interpreter`

### Hash routing: article selection must not change `window.location.hash`
`App.svelte` listens to `hashchange` and switches the entire route based on the hash.
If `ThreadTree.svelte` changes the hash when selecting an article (e.g. `#/article/...`),
App.svelte unmounts `Thread.svelte`, destroying all article state — the selected article
immediately disappears.
Article selection state lives in the `selectedArticleId` store only; no hash change needed.
- **Where:** `frontend/src/components/ThreadTree.svelte → selectArticle()`

### Test runs write `test-token-xyz` to the real config file
Tests use a hardcoded token. If `pytest` has been run on this machine, `~/.config/reticulum-newsnet/config.toml`
will contain `api_token = "test-token-xyz"`. Since `is_first_run()` returns false when any token is set,
the wizard won't regenerate it. Replace it manually or delete the config to re-trigger the wizard.

### `_lifespan_enabled=False` in tests
`create_app()` accepts `_lifespan_enabled: bool = True`. Tests pass `False` to skip `node.start()`,
which requires real RNS. The 503-during-startup test passes `startup_state="starting"` + `_lifespan_enabled=False`.

### Frontend is plain Vite + Svelte, not SvelteKit
Routing is hash-based (`#/`, `#/group/...`, `#/peers`, etc.) handled manually in `App.svelte`.
There are no file-based routes, no `+page.svelte` files, no server-side rendering. Do not scaffold
or restructure this as SvelteKit.

### Local auth endpoint bypasses token for localhost
`GET /api/local-auth` returns the bearer token with no auth required, but only for requests from
`127.0.0.1` / `::1`. The frontend calls this on mount to auto-connect without user interaction.
Do not add this endpoint to the 503 startup guard — it needs to be reachable during STARTING state.
(Currently it isn't guarded because it's registered before the middleware runs on `/api/*`.)

### `config.save()` uses hand-rolled TOML — no external lib
`newsnet/config.py → save()` serializes manually to avoid adding a TOML-write dependency.
It only writes known dataclass fields and does not preserve `[[interface]]` blocks or comments.
If you need to preserve those, read the file first and merge carefully.

### `ThreadTree` recursive self: pass full article list, not just children
`<svelte:self>` must receive the **full** `articles` array, not just the children of the current node.
If you pass only children (`tree.get(root.message_id)`), the recursive instance runs `buildTree` on
that subset — every article in the subset has a non-null `references` field, so `tree.get(null)` is
always empty and nothing renders. Depth is controlled via the `parentId` prop, not by slicing the list.
- **Where:** `frontend/src/components/ThreadTree.svelte`

### Pull model security: `_requested_ids` in SyncSession
Articles received during sync are only written to the store if their `message_id` was in the
outbound `ArticleRequestMessage` for that session (`SyncSession._requested_ids`). This prevents
a remote peer from pushing unsolicited content. Do not bypass this check.
- **Where:** `newsnet/sync.py → SyncSession._on_article_data()`, `_resource_concluded()`
