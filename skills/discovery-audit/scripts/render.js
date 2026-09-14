#!/usr/bin/env node
'use strict';
/**
 * Optional Node renderer.
 * SECURITY NOTE — jsdom runs with runScripts:'dangerously' in an ephemeral
 * Node sandbox. No cookies, credentials, or persistent storage are available
 * to the rendered page.
 */

const http = require('http');
const https = require('https');

const UA = 'Mozilla/5.0 (compatible; AI-Readiness-Auditor/1.0)';
const UA_TOKEN = 'ai-readiness-auditor';

function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function matchesPath(pattern, path) {
  if (!pattern) return false;
  const endAnchored = pattern.endsWith('$');
  const core = endAnchored ? pattern.slice(0, -1) : pattern;
  const regex = '^' + (core === '/'
    ? '/'
    : core.split('*').map(escapeRegex).join('.*')
  ) + (endAnchored ? '$' : '');
  try { return new RegExp(regex).test(path); } catch (e) { return false; }
}

function matchedLength(pattern, path) {
  const endAnchored = pattern.endsWith('$');
  const core = endAnchored ? pattern.slice(0, -1) : pattern;
  const regex = '^' + (core === '/'
    ? '/'
    : core.split('*').map(escapeRegex).join('.*')
  ) + (endAnchored ? '$' : '');
  try {
    const m = path.match(new RegExp(regex));
    return m ? m[0].length : -1;
  } catch (e) { return -1; }
}

function agentMatches(agent, ours) {
  if (agent === ours) return true;
  return agent.startsWith(ours + '/');
}

function isAllowedByRobots(robotsTxt, path) {
  if (!robotsTxt) return true;
  const groups = [];
  let current = null;
  for (const raw of robotsTxt.split(/\r?\n/)) {
    const line = raw.split('#')[0].trim();
    if (!line) { current = null; continue; }
    const idx = line.indexOf(':');
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim().toLowerCase();
    const val = line.slice(idx + 1).trim();
    if (key === 'user-agent') {
      if (!current || current.rules.length) {
        current = { agents: [], rules: [] };
        groups.push(current);
      }
      if (val) current.agents.push(val.toLowerCase());
    } else if (key === 'allow' || key === 'disallow') {
      if (!current) { current = { agents: ['*'], rules: [] }; groups.push(current); }
      current.rules.push([key, val]);
    }
  }

  let matched = groups.filter(g => g.agents.some(a => agentMatches(a, UA_TOKEN)));
  if (matched.length === 0) matched = groups.filter(g => g.agents.some(a => a === '*'));
  if (matched.length === 0) return true;

  let bestRule = null, bestLen = -1;
  for (const g of matched) {
    for (const [kind, pat] of g.rules) {
      if (!pat) continue;
      const consumed = matchedLength(pat, path);
      if (consumed < 0) continue;
      if (consumed > bestLen || (consumed === bestLen && kind === 'allow')) {
        bestLen = consumed; bestRule = kind;
      }
    }
  }
  return bestRule !== 'disallow';
}
const MAX_BYTES = 1024 * 1024;

function httpGet(target, timeoutMs = 15000) {
  return new Promise((resolve) => {
    const lib = target.startsWith('https') ? https : http;
    const req = lib.get(target, { timeout: timeoutMs, headers: { 'User-Agent': UA } }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        const next = new URL(res.headers.location, target).toString();
        res.resume();
        return resolve(httpGet(next, timeoutMs));
      }

      // Content-type gate: skip non-HTML.
      const ct = String(res.headers['content-type'] || '').toLowerCase();
      const isHtml = ct.includes('text/html') || ct.includes('application/xhtml+xml');
      if (res.statusCode === 200 && !isHtml) {
        res.resume();
        return resolve({
          ok: false,
          body: '',
          status: res.statusCode,
          error: `unsupported content-type: ${ct || 'none'}`
        });
      }

      let body = '';
      let bytes = 0;
      let aborted = false;
      res.setEncoding('utf8');

      res.on('data', (c) => {
        if (aborted) return;

        bytes += Buffer.byteLength(c);

        if (bytes > MAX_BYTES) {
          aborted = true;
          req.destroy();
          resolve({
            ok: false,
            body: '',
            status: res.statusCode,
            error: 'response too large'
          });
          return;
        }

        body += c;
      });

      res.on('end', () => {
        if (!aborted) {
          resolve({ ok: true, body, status: res.statusCode });
        }
      });
    });

    req.on('error', () => resolve({
      ok: false,
      body: '',
      status: 0
    }));

    req.on('timeout', () => {
      req.destroy();
      resolve({
        ok: false,
        body: '',
        status: 0
      });
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { isAllowedByRobots, matchesPath, matchedLength, agentMatches };
}

if (require.main === module) {
  (async () => {
    const url = process.argv[2];
    if (!url) { console.log(JSON.stringify({ html: '', error: 'no url' })); return; }

    const parsed = new URL(url);
    const origin = `${parsed.protocol}//${parsed.host}`;
    const path = parsed.pathname + (parsed.search || '');

    const robots = await httpGet(origin + '/robots.txt', 5000);
    if (robots.ok && !isAllowedByRobots(robots.body, path)) {
      console.log(JSON.stringify({ html: '', error: 'blocked by robots.txt' }));
      return;
    }

    let html = '';
    let jsdom = null;
    try { jsdom = require('jsdom'); } catch (e) { jsdom = null; }

    const fetched = await httpGet(url);
    if (!fetched.ok || !fetched.body) {
      console.log(JSON.stringify({ html: '', error: 'fetch failed' }));
      return;
    }

    if (jsdom && jsdom.JSDOM) {
      try {
        const dom = new jsdom.JSDOM(fetched.body, {
          runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
        });
        await new Promise((r) => setTimeout(r, 1500));
        html = dom.serialize();
      } catch (e) { html = fetched.body; }
    } else {
      html = fetched.body;
    }
    console.log(JSON.stringify({ html, error: null }));
  })();
}