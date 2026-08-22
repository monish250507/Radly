import dotenv from 'dotenv';

dotenv.config();

const NODE_ENV = process.env.NODE_ENV || 'development';
const IS_VERCEL = Boolean(process.env.VERCEL);

export const config = {
  env: NODE_ENV,
  isProduction: NODE_ENV === 'production' || IS_VERCEL,
  isVercel: IS_VERCEL,
  runtimeMode: IS_VERCEL ? 'vercel-serverless' : 'standalone-node',
  port: Number(process.env.PORT) || 5000,
  logLevel: process.env.LOG_LEVEL || '',
  service: {
    name: 'paperblast-impact-analyzer',
    friendlyName: 'PaperBlast Impact Analyzer Engine'
  },
  groq: {
    get apiKey() {
      return process.env.GROQ_API_KEY || '';
    },
    get configured() {
      return Boolean(process.env.GROQ_API_KEY);
    }
  }
};
