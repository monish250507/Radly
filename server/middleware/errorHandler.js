import { requestStore, logger } from '../logger.js';
import { AppError } from '../errors.js';
import { config } from '../config.js';

export function apiNotFound(req, res, next) {
  if (!req.path.startsWith('/api')) return next();
  res.status(404).json({
    error: `No API route matches ${req.method} ${req.path}`,
    code: 'route_not_found',
    requestId: requestStore.getStore()?.requestId
  });
}

export function errorHandler(err, req, res, next) {
  const isAppError = err instanceof AppError;
  let statusCode = err.statusCode || 500;
  let code = isAppError ? err.code : 'internal_error';

  if (err.type === 'entity.parse.failed') {
    statusCode = 400;
    code = 'invalid_json_body';
  }

  const meta = {
    code,
    statusCode,
    method: req.method,
    path: req.path,
    stack: config.isProduction ? undefined : err.stack
  };
  if (statusCode >= 500) {
    logger.error(err.message || 'Unhandled error', meta);
  } else {
    logger.warn(err.message || 'Request error', meta);
  }

  if (res.headersSent) {
    return next(err);
  }

  const exposeMessage = err.expose !== false;
  res.status(statusCode).json({
    error: exposeMessage ? (err.message || 'Internal server error') : 'Internal server error',
    code,
    requestId: requestStore.getStore()?.requestId
  });
}
