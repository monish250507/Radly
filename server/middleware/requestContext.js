import { randomUUID } from 'node:crypto';
import { requestStore } from '../logger.js';
import { logger } from '../logger.js';

export function requestContext(req, res, next) {
  const requestId = req.headers['x-request-id'] || randomUUID();
  res.setHeader('x-request-id', requestId);

  const start = Date.now();
  requestStore.run({ requestId, method: req.method, path: req.path }, () => {
    res.on('finish', () => {
      logger.info('request completed', {
        method: req.method,
        path: req.path,
        statusCode: res.statusCode,
        durationMs: Date.now() - start
      });
    });
    next();
  });
}
