// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
/**
 * OAuth2 "authorization_code" login against Nx Cloud, then browse one
 * site's servers and cameras.
 *
 * The functions below are declared in roughly the order they're used.
 *
 *   STEP 1  Check the page's own URL for a `code` - are we returning
 *           from login, or is this the very first visit?
 *   STEP 2  No code yet, so send the browser to Nx Cloud to log in.
 *   STEP 3  The user logs in on Nx Cloud itself. This page is not
 *           involved and never sees a password.
 *   STEP 4  Nx Cloud redirects back here with a one-time `code`.
 *   STEP 5  Trade that `code` for an access_token + refresh_token.
 *   STEP 6  Use the access_token to list the account's sites and draw
 *           one button per site.
 *   STEP 7  Clicking a site's button trades the refresh_token for a
 *           token scoped to just that site, then reads its servers and
 *           cameras through Nx Cloud's relay.
 *   STEP 8  Draw the servers and cameras as tiles.
 */

let tokens, access_token, refresh_token;
const url = new URL(window.location.href);
const cloudHost = 'https://nxvms.com';

// GET against the cdb (Cloud DB) API, authenticated with access_token
// when one is available.
const getWrapper = (url, params) => {
  const requestUrl = new URL(url);
  requestUrl.search = new URLSearchParams(params).toString();
  const options = {
    method: "GET",
    headers: {},
  };
  if (access_token) {
    options.headers['Authorization'] = `Bearer ${access_token}`
  }
  return fetch(requestUrl.toString(), options).then(r => r.json());
};

// POST used for both token exchanges below.
const postWrapper = (url, data) => {
  const options = {
    headers: {
      'Content-Type': 'application/json'
    },
    method: "POST",
    body: JSON.stringify(data)
  };
  return fetch(url, options).then(r => r.json());
};


/* ================================================================
 * Send the browser to Nx Cloud to log in
 * ================================================================
 * This is a full-page redirect, not a fetch() call - it navigates the
 * browser to nxvms.com directly, the same way clicking a link would.
 *
 * The callback parameter is named `redirect_url`, NOT the
 * `redirect_uri`. Nx Cloud's own docs call this out explicitly.
 */
const buildOauthUrl = () => {
  const redirectUrl = new URL(`${cloudHost}/authorize`);
  redirectUrl.searchParams.set('redirect_url', window.location.href);
  redirectUrl.searchParams.set('client_id', 'api-tool');
  return redirectUrl.toString();
};

const redirectOauthLogin = (cloudAuthUrl) => {
  window.location.href = cloudAuthUrl;
};


/* ================================================================
 * Clean up the URL after Nx Cloud redirects back
 * ================================================================
 * Once the `code` has been used, it serves no further purpose - codes
 * are single-use, so a stale one left sitting in the address bar or
 * browser history is just noise. pushState() rewrites the URL in
 * place, without reloading the page.
 */
const cleanupCode = () => {
  url.searchParams.delete('code');
  window.history.pushState({}, undefined, url.toString());
};


/* ================================================================
 * Exchange the code for real tokens
 * ================================================================
 */
const getTokensWithCode = (code) => {
  const data = {
    code,
    grant_type: 'authorization_code',
    response_type: 'token'
  };
  return postWrapper(`${cloudHost}/cdb/oauth2/token`, data);
};


/* ================================================================
 * Call a site through the relay
 * ================================================================
 * getTokenForSystem() swaps refresh_token for a token scoped to one
 * site (grant_type=refresh_token, scope=cloudSystemId=<id>).
 *
 * The relay (*.relay.vmsproxy.com) answers with an HTTP 307 to the
 * region-specific relay host. Browsers drop the Authorization header
 * across that redirect, so resolveRelayRedirect() makes one bare
 * request first to resolve the final URL. systemGetWrapper() then
 * sends the real, authenticated request straight there - no further
 * redirect, so the header survives.
 */
const getTokenForSystem = (systemId) => {
  const data = {
    refresh_token,
    grant_type: "refresh_token",
    response_type: "token",
    scope: `cloudSystemId=${systemId}`
  };
  return postWrapper(`${cloudHost}/cdb/oauth2/token`, data).then((data) => data.access_token);
};

const resolveRelayRedirect = async (url) => {
  const probeResponse = await fetch(url.toString());
  return probeResponse.url;
};

const systemGetWrapper = async (systemToken, url, params) => {
  const requestUrl = new URL(url);
  requestUrl.search = new URLSearchParams(params).toString();
  const finalUrl = await resolveRelayRedirect(requestUrl);
  const options = {
    method: "GET",
    headers: {},
  };
  if (systemToken) {
    options.headers['Authorization'] = `Bearer ${systemToken}`
  }
  return fetch(finalUrl, options).then(r => r.json());
};


/* Render the servers and their cameras as tiles. */
const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

const renderResourceTree = (systemName, resourceTree) => {
  const dataDiv = document.getElementById('data');
  const cards = Object.values(resourceTree).map(({name, cameras}) => {
    const cameraItems = cameras.length
      ? cameras.map(({name: cameraName, status}) => `
          <li>${escapeHtml(cameraName)} - ${escapeHtml(status || 'No status')}</li>`).join('')
      : '<li class="camera-empty">No cameras</li>';
    return `
      <div class="server-card">
        <h3>${escapeHtml(name)}</h3>
        <ul class="camera-list">${cameraItems}</ul>
      </div>`;
  }).join('');

  dataDiv.innerHTML = `
    <h2>Cameras on ${escapeHtml(systemName)}</h2>
    <div class="server-grid">${cards}</div>`;
};


/* ================================================================
 * Draw one button per site
 * ================================================================
 * Each button's onclick runs STEP 7 (get a site-scoped token, call
 * the relay) then STEP 8 (render the result) - only once clicked.
 */
// Above this many sites, show a filter box + scrollbar instead of a
// plain wrapping row.
const FILTER_THRESHOLD = 8;

const createButtons = (systems) => {
  const systemsDiv = document.getElementById('systems');
  const filterInput = document.getElementById('systemFilter');
  const sortedSystems = [...systems].sort((a, b) => a.name.localeCompare(b.name));

  if (sortedSystems.length > FILTER_THRESHOLD) {
    systemsDiv.classList.add('scrollable');
    filterInput.style.display = '';
    filterInput.addEventListener('input', () => {
      const query = filterInput.value.trim().toLowerCase();
      systemsDiv.querySelectorAll('button').forEach((button) => {
        button.classList.toggle('hidden-by-filter', !button.dataset.name.includes(query));
      });
    });
  }

  sortedSystems.forEach(({name, id, version}) => {
    const button = document.createElement('button');
    const cloudRelay = `https://${id}.relay.vmsproxy.com`;
    button.innerText = name;
    button.dataset.name = name.toLowerCase();
    button.disabled = !version || parseInt(version[0]) < 5;
    button.onclick = async () => {
      // Highlight whichever site button was just clicked.
      systemsDiv.querySelectorAll('button.active').forEach((b) => b.classList.remove('active'));
      button.classList.add('active');

      // STEP 7 - get a token scoped to this one site, then call it
      // through the relay for its servers and cameras.
      const systemAccessToken = await getTokenForSystem(id);
      const servers = await systemGetWrapper(systemAccessToken, `${cloudRelay}/rest/v4/servers`);
      const cameras = await systemGetWrapper(systemAccessToken, `${cloudRelay}/rest/v4/devices`);

      // Group the flat camera list under the server that owns each one.
      const resourceTree = servers.reduce((resources, {id, name}) => {
        resources[id] = {
          name,
          cameras: []
        };
        return resources;
      }, {});
      cameras.forEach(({id, name: cameraName, serverId, status}) => {
        if (serverId in resourceTree) {
          resourceTree[serverId].cameras.push({name: cameraName, status});
        }
      });

      // STEP 8 - draw the result.
      renderResourceTree(name, resourceTree);
    };
    systemsDiv.appendChild(button);
  });
};


/* ================================================================
 * Main flow - runs once, as soon as the page loads
 * ================================================================
 * This is the entry point. Start reading here - every step below
 * jumps up to the function that does the actual work, then comes
 * back down to the next step.
 */
(async () => {
  // STEP 1 - Is there already a `code` in our own URL? If Nx Cloud
  // hasn't redirected back to us yet, there won't be - so kick off
  // STEP 2 (send the browser to Nx Cloud to log in) and stop here.
  // STEPs 3 and 4 happen outside of this page, on Nx Cloud's side and
  // then back through the browser's address bar.
  const code = url.searchParams.get('code');
  if (!code) {
    return redirectOauthLogin(buildOauthUrl());
  }
  cleanupCode();

  // STEP 5 - We have a code. Exchange it for tokens.
  tokens = await getTokensWithCode(code);
  access_token = tokens.access_token;
  refresh_token = tokens.refresh_token;

  // STEP 6 - Use the access_token to list the Nx Cloud sites this
  // account can see, then draw one button per site.
  const systemsResponse = await getWrapper(`${cloudHost}/cdb/systems`);
  // The cdb API wraps the array under different keys depending on
  // deployment; fall back to the raw response if it's a bare array.
  const systems = systemsResponse.systems || systemsResponse.reply || systemsResponse.data || systemsResponse;
  createButtons(systems);

  // STEPs 7 and 8 happen later, on demand, when a site's button is
  // clicked - see createButtons() above.
})();
