import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { exec } from 'child_process';
import { promisify } from 'util';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';

import { extractCodeSymbols } from './codeParser.js';
import { extractTextFromDocument, parsePaperStructure } from './paperParser.js';
import { calculateBlastRadius } from './impactEngine.js';
import { config } from './config.js';
import { logger } from './logger.js';
import { ValidationError, NotFoundError, asyncHandler } from './errors.js';
import { requestContext } from './middleware/requestContext.js';
import { apiNotFound, errorHandler } from './middleware/errorHandler.js';
import { getVersionInfo } from './versionInfo.js';

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = config.port;

app.use(cors());
app.use('/api', requestContext);
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Serve built frontend assets in standalone mode
const distPath = path.join(__dirname, '../dist');
if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
}

// Serverless-safe scratch temp directory (Uses /tmp on Vercel)
const scratchDir = path.join(os.tmpdir(), 'paperblast_scratch');
if (!fs.existsSync(scratchDir)) {
  try {
    fs.mkdirSync(scratchDir, { recursive: true });
  } catch (e) {}
}

// Helper for fetch with strict network timeout
async function fetchWithTimeout(url, options = {}, timeoutMs = 4000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

/**
 * 100% Real-Time High-Speed GitHub Repository Ingestion Engine.
 * Supports git clone --depth 1 with HTTP zip fallbacks.
 */
app.post('/api/ingest-github', asyncHandler(async (req, res) => {
  const { repoUrl, codeFiles: directFiles } = req.body;

  if (directFiles && Array.isArray(directFiles)) {
    const symbols = extractCodeSymbols(directFiles);
    return res.json({
      success: true,
      repo: 'Direct Upload',
      fileCount: directFiles.length,
      files: directFiles.map(f => ({ path: f.name || f.path, lineCount: (f.content || '').split('\n').length })),
      symbols
    });
  }

  if (!repoUrl) {
    throw new ValidationError('Repository URL or code files required.');
  }

  const cleanUrl = repoUrl.replace(/\/$/, '').replace(/\.git$/, '');
  const match = cleanUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);

  if (!match) {
    throw new ValidationError('Invalid GitHub repository URL structure.');
  }

    const owner = match[1];
    const repo = match[2];
    const codeFiles = [];
    const validExtensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.cpp', '.cu', '.h', '.c', '.rs', '.go'];

    // Strategy 1: High-Speed git clone --depth 1 --filter=blob:none (30s timeout)
    const targetDir = path.join(scratchDir, `repo_${owner}_${repo}_${Date.now()}`);
    try {
      await execAsync(`git clone --depth 1 --filter=blob:none ${cleanUrl}.git "${targetDir}"`, { timeout: 30000 });

      if (fs.existsSync(targetDir)) {
        const readFilesRecursively = (dir, relPath = '') => {
          const items = fs.readdirSync(dir);
          for (const item of items) {
            if (item === '.git' || item === 'node_modules' || item === 'venv' || item === '__pycache__' || item.startsWith('.')) continue;
            const fullPath = path.join(dir, item);
            const relativeItemPath = relPath ? `${relPath}/${item}` : item;
            const stat = fs.statSync(fullPath);

            if (stat.isDirectory()) {
              readFilesRecursively(fullPath, relativeItemPath);
            } else if (stat.isFile()) {
              const ext = path.extname(item).toLowerCase();
              if (validExtensions.includes(ext) && !relativeItemPath.includes('/test')) {
                try {
                  const content = fs.readFileSync(fullPath, 'utf8');
                  codeFiles.push({ path: relativeItemPath, content });
                } catch (e) {}
              }
            }
          }
        };

        readFilesRecursively(targetDir);
      }
    } catch (gitErr) {
      logger.warn('git clone skipped/failed', { reason: gitErr.message, repo: `${owner}/${repo}` });
    } finally {
      if (fs.existsSync(targetDir)) {
        fs.rm(targetDir, { recursive: true, force: true }, () => {});
      }
    }

    // Strategy 2: ZIP archive download fallback
    if (codeFiles.length === 0) {
      for (const branch of ['main', 'master', 'dev']) {
        try {
          const zipUrl = `https://codeload.github.com/${owner}/${repo}/zip/refs/heads/${branch}`;
          const zipRes = await fetchWithTimeout(zipUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
          }, 6000);

          if (zipRes.ok) {
            const arrayBuffer = await zipRes.arrayBuffer();
            const zip = await JSZip.loadAsync(arrayBuffer);

            const entries = Object.keys(zip.files).filter(fn => {
              const ext = path.extname(fn).toLowerCase();
              return !zip.files[fn].dir && validExtensions.includes(ext) && !fn.includes('/test') && !fn.includes('/venv');
            }).slice(0, 30);

            for (const filename of entries) {
              const content = await zip.files[filename].async('string');
              const cleanPath = filename.substring(filename.indexOf('/') + 1);
              codeFiles.push({ path: cleanPath, content });
            }

            if (codeFiles.length > 0) break;
          }
        } catch (e) {}
      }
    }

    if (codeFiles.length === 0) {
      throw new NotFoundError(`Unable to fetch repository source files for ${owner}/${repo}. Please check the URL or use 'Choose Code Files' to upload Python/JS files directly.`, 'repo_unreachable');
    }

    const selectedFiles = codeFiles.slice(0, 30);
    const symbols = extractCodeSymbols(selectedFiles);

    res.json({
      success: true,
      repo: `${owner}/${repo}`,
      fileCount: selectedFiles.length,
      files: selectedFiles.map(f => ({ path: f.path, lineCount: (f.content || '').split('\n').length })),
      symbols
    });
}));

// Parse Paper Endpoint (100% Dynamic PDF / DOCX / LaTeX Extractor)
app.post('/api/parse-paper', asyncHandler(async (req, res) => {
    const { paperText, paperFileBase64, fileType } = req.body;
    let rawText = '';

    if (paperFileBase64) {
      const buffer = Buffer.from(paperFileBase64, 'base64');
      rawText = await extractTextFromDocument(buffer, fileType || 'pdf');
    } else if (paperText) {
      rawText = paperText;
    } else {
      throw new ValidationError('Paper text string or document file required.');
    }

    const paperAST = parsePaperStructure(rawText);

    res.json({
      success: true,
      extractedLength: rawText.length,
      paperAST
    });
}));

// Analyze Impact Endpoint (100% Dynamic Blast Radius Engine)
app.post('/api/analyze-impact', asyncHandler(async (req, res) => {
    const { codeSymbols, paperAST, query } = req.body;

    if (!query) {
      throw new ValidationError('Change query string required.');
    }

    if (!codeSymbols || !Array.isArray(codeSymbols)) {
      throw new ValidationError('Code symbols array required.');
    }

    if (!paperAST || !paperAST.sections) {
      throw new ValidationError('Paper AST required.');
    }

    const analysis = await calculateBlastRadius(codeSymbols, paperAST, query);

    res.json({
      success: true,
      analysis
    });
}));

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'OK',
    service: config.service.friendlyName,
    timestamp: new Date().toISOString(),
    groqConfigured: config.groq.configured,
    version: getVersionInfo()
  });
});

app.use(apiNotFound);

// SPA Fallback in standalone server mode
app.get('*', (req, res) => {
  if (fs.existsSync(path.join(__dirname, '../dist/index.html'))) {
    res.sendFile(path.join(__dirname, '../dist/index.html'));
  } else {
    res.send('PaperBlast API Running.');
  }
});

app.use(errorHandler);

// Export app for Vercel serverless execution
export default app;

// Listen on port only when running locally (not on Vercel)
if (!config.isVercel) {
  app.listen(PORT, () => {
    logger.info(`PaperBlast server listening`, { port: PORT, env: config.env, runtimeMode: config.runtimeMode, version: getVersionInfo().version });
  });
}
