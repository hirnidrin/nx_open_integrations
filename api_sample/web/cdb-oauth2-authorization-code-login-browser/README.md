# Cloud CDB — OAuth2 authorization_code login

Authorize an external web app against Nx Cloud using the real, redirect-based
OAuth2 `authorization_code` grant — the flow a production app should use —
then list the account's Sites and drill into one Site's servers and cameras
through the Cloud relay.

## Prerequisites

- [Node.js v18+](https://nodejs.org/) (npm included). 
- Nx Cloud account with a Site attached.

## How the Flow Works

`cdb-oauth2-authentication-webapp.js` labels every step below with a
matching `STEP n` comment, in the order it actually executes:

1. The page checks its own URL for a `code` query parameter. On first load
   there isn't one.
2. `buildOauthUrl()` builds `https://nxvms.com/authorize?redirect_url=...&client_id=...`
   and the page navigates there.
3. The user logs into Nx Cloud (outside this page — it never sees a
   password).
4. Nx Cloud redirects back to this page with a one-time `code` in the URL;
   `cleanupCode()` removes it from the address bar once used.
5. `getTokensWithCode()` trades `code` for a cloud-wide `access_token` and
   `refresh_token` via `POST /cdb/oauth2/token`.
6. The `access_token` lists this account's Sites (`GET /cdb/systems`) and
   the page draws one button per Site, sorted by name. Past 8 Sites, a
   filter box and a scrollbar appear so the list stays easy to scan.
7. Clicking a Site's button calls `getTokenForSystem()`, which trades the
   `refresh_token` for a token scoped to that Site
   (`grant_type=refresh_token`, `scope=cloudSystemId={id}`), then reads that
   Site's servers and cameras through the Cloud relay
   (`/rest/v4/servers`, `/rest/v4/devices`).
8. The servers and their cameras are rendered as tiles.

## Setup and Run

```bash
npm install
npm run start
```

Open the printed URL (default `http://localhost:8080`). You'll be redirected
to Nx Cloud to log in, then back to this page.

> Replace `client_id: 'api-tool'` inside `cdb-oauth2-authentication-webapp.js` with your own client id.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The demo markup only. |
| `cdb-oauth2-authentication-webapp.js` | The logic. Follows the numbered flow above. |
| `style.css` | Presentation only (server tiles, camera bullet list). |
| `package.json` | Local dev server (`http-server`). |
| `README.md` | You are here. |

## Notes

- The authorization `code` is single-use — no need to persist it.
- Revoke a token via `DELETE /cdb/oauth2/token/{token}`. (_When a refresh token is deleted, no access tokens are invalidated._)

## Reference

For more detail, see the [Nx Support portal: API Cloud OAuth](https://support.networkoptix.com/hc/en-us/sections/32712188971671-API-Cloud-OAuth).
