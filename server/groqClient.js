import { config } from './config.js';
import { logger } from './logger.js';
import { UpstreamError } from './errors.js';

const GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions';

/**
 * Call Groq API with temperature 0.0 for high-precision deterministic text synthesis.
 * Uses User-Agent header to prevent perimeter blocking.
 */
export async function callGroqAPI(messages, systemPrompt = '', responseFormatJson = true) {
  const modelsToTry = ['groq/compound', 'qwen/qwen3.6-27b', 'openai/gpt-oss-120b'];
  let lastError = null;

  if (!config.groq.configured) {
    throw new UpstreamError('GROQ_API_KEY is not configured; AI synthesis unavailable.', {
      statusCode: 503,
      code: 'ai_not_configured'
    });
  }

  const fullMessages = [];
  if (systemPrompt) {
    fullMessages.push({ role: 'system', content: systemPrompt });
  }
  fullMessages.push(...messages);

  for (const model of modelsToTry) {
    try {
      const payload = {
        model,
        messages: fullMessages,
        temperature: 0.0, // Strictly deterministic for maximum precision
        max_tokens: 4096
      };

      if (responseFormatJson) {
        payload.response_format = { type: 'json_object' };
      }

      const response = await fetch(GROQ_ENDPOINT, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${config.groq.apiKey}`,
          'Content-Type': 'application/json',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        logger.warn(`Groq model ${model} returned status ${response.status}`, { model, statusCode: response.status });
        lastError = new Error(`Groq API HTTP ${response.status}: ${errorText}`);
        continue;
      }

      const data = await response.json();
      const content = data.choices[0]?.message?.content;
      if (!content) {
        throw new Error('Groq returned empty response body');
      }

      if (responseFormatJson) {
        try {
          return JSON.parse(content);
        } catch (jsonErr) {
          // If JSON parsing fails, extract json block using regex
          const match = content.match(/\{[\s\S]*\}/);
          if (match) {
            return JSON.parse(match[0]);
          }
          throw jsonErr;
        }
      }

      return content;
    } catch (err) {
      logger.error(`Failed with Groq model ${model}`, { model, reason: err.message });
      lastError = err;
    }
  }

  throw lastError || new Error('All Groq API models failed');
}
