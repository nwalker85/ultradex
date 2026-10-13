// Local dev runtime for the Ultradex job-search dashboard.
// Not committed to git (untracked, local-only). Secrets are never hardcoded
// here — they are read at PM2-start time from the gitignored, chmod-600
// `.env` file in this same worktree.
'use strict';

const fs = require('fs');
const path = require('path');

function loadEnvFile(filePath) {
  const env = {};
  const contents = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of contents.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    env[key] = value;
  }
  return env;
}

const ROOT = __dirname;
const fileEnv = loadEnvFile(path.join(ROOT, '.env'));
const PYTHON = path.join(ROOT, '.venv', 'bin', 'python');
const UVICORN = path.join(ROOT, '.venv', 'bin', 'uvicorn');

module.exports = {
  apps: [
    {
      name: 'ultradex-api',
      cwd: ROOT,
      script: UVICORN,
      interpreter: 'none',
      args: 'api.main:app --host 127.0.0.1 --port 8000',
      env: fileEnv,
      autorestart: true,
      max_restarts: 10,
      out_file: path.join(ROOT, 'logs', 'ultradex-api-out.log'),
      error_file: path.join(ROOT, 'logs', 'ultradex-api-error.log'),
      time: true,
    },
    {
      name: 'ultradex-worker',
      cwd: ROOT,
      script: PYTHON,
      interpreter: 'none',
      args: '-m core.jobsearch_worker',
      env: fileEnv,
      autorestart: true,
      max_restarts: 10,
      out_file: path.join(ROOT, 'logs', 'ultradex-worker-out.log'),
      error_file: path.join(ROOT, 'logs', 'ultradex-worker-error.log'),
      time: true,
    },
  ],
};
