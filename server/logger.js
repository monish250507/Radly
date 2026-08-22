import { AsyncLocalStorage } from 'node:async_hooks';
import { config } from './config.js';

export const requestStore = new AsyncLocalStorage();

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const configuredLevel = LEVELS[config.logLevel] || (config.isProduction ? LEVELS.info : LEVELS.debug);

function write(level, message, meta = {}) {
  if (LEVELS[level] < configuredLevel) return;
  const ctx = requestStore.getStore() || {};
  const entry = {
    ts: new Date().toISOString(),
    level,
    service: config.service.name,
    env: config.env,
    requestId: ctx.requestId,
    msg: message,
    ...meta
  };
  const line = JSON.stringify(entry);
  if (level === 'error') console.error(line);
  else if (level === 'warn') console.warn(line);
  else console.log(line);
}

export const logger = {
  debug: (msg, meta) => write('debug', msg, meta),
  info: (msg, meta) => write('info', msg, meta),
  warn: (msg, meta) => write('warn', msg, meta),
  error: (msg, meta) => write('error', msg, meta),
  child(baseMeta = {}) {
    return {
      debug: (msg, meta) => write('debug', msg, { ...baseMeta, ...meta }),
      info: (msg, meta) => write('info', msg, { ...baseMeta, ...meta }),
      warn: (msg, meta) => write('warn', msg, { ...baseMeta, ...meta }),
      error: (msg, meta) => write('error', msg, { ...baseMeta, ...meta })
    };
  }
};
