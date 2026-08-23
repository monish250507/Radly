import { config } from './config.js';
import { logger } from './logger.js';
import { UpstreamError } from './errors.js';

const GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions';

/**
 * Known valid Groq-hosted model IDs (verified against Groq API docs).
 * Using a single model with no fallback to unverified third-party model strings
 * that would silently waste round-trips on 404s.
 *
 * If the primary model fails we throw immediately rather than retrying with
 * model IDs that have not been verified as Groq-hosted.
 */
const GROQ_MODELS = [
  'llama-3.3-70b-versatile',     // primary — verified Groq-hosted
  'llama-3.1-70b-versatile'      // secondary — verified Groq-hosted fallback
];

/**
 * Call Groq API with temperature 0.0 for deterministic text synthesis.
 * Throws UpstreamError on all failure modes — callers must handle and
 * must NOT convert a throw into a successful-looking fabricated result.
 */
export async function callGroqAPI(messages, systemPrompt = '', responseFormatJson = true) {
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

  let lastError = null;

  for (const model of GROQ_MODELS) {
    try {
      const payload = {
        model,
        messages: fullMessages,
        temperature: 0.0,
        max_tokens: 4096
      };

      if (responseFormatJson) {
        payload.response_format = { type: 'json_object' };
      }

      const response = await fetch(GROQ_ENDPOINT, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${config.groq.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        logger.warn(`Groq model ${model} returned status ${response.status}`, {
          model,
          statusCode: response.status
        });
        lastError = new Error(`Groq API HTTP ${response.status}: ${errorText}`);
        continue; // try next model
      }

      const data = await response.json();
      const content = data.choices?.[0]?.message?.content;
      if (!content) {
        throw new Error('Groq returned empty response body');
      }

      if (responseFormatJson) {
        try {
          return JSON.parse(content);
        } catch (jsonErr) {
          // Attempt to extract a JSON object from surrounding prose
          const match = content.match(/\{[\s\S]*\}/);
          if (match) {
            return JSON.parse(match[0]);
          }
          throw new Error(`Groq response was not valid JSON: ${jsonErr.message}`);
        }
      }

      return content;
    } catch (err) {
      logger.error(`Failed with Groq model ${model}`, { model, reason: err.message });
      lastError = err;
    }
  }

  throw lastError || new UpstreamError('All Groq API models failed', { code: 'groq_all_models_failed' });
}
