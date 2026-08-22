export class AppError extends Error {
  constructor(message, { statusCode = 500, code = 'internal_error', expose = true, cause } = {}) {
    super(message);
    this.name = 'AppError';
    this.statusCode = statusCode;
    this.code = code;
    this.expose = expose;
    this.cause = cause;
  }
}

export class ValidationError extends AppError {
  constructor(message, code = 'validation_error') {
    super(message, { statusCode: 400, code });
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends AppError {
  constructor(message, code = 'not_found') {
    super(message, { statusCode: 404, code });
    this.name = 'NotFoundError';
  }
}

export class UpstreamError extends AppError {
  constructor(message, { statusCode = 502, code = 'upstream_failure', cause } = {}) {
    super(message, { statusCode, code, cause });
    this.name = 'UpstreamError';
  }
}

export function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
