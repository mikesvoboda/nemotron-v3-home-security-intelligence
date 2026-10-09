#!/usr/bin/env node
// Fake verdict engine for REHEARSING the B1.4 real-tier command sequence without a GPU.
//
// It answers the three endpoints the flow touches: /health (what the readiness probe dials,
// backend/api/routes/system.py:912-941), /props (what operator.md step 3 records), and
// /v1/chat/completions (a canned completion, in case a rehearsal wants a request through).
//
// IT IS NOT THE PRODUCTION PIN. The real tier is about the sha256-pinned Q4_K_M pair that
// `agent-gpu run` serves (docs/uplevel/operator.md step 1); this answers with constants.
// A run against this mock is a rehearsal of the commands and must be posted as such, never
// as the real tier.
//
// B14_MOCK=1 is set by the compose service so a human (and the operator) can tell from
// /props that no GPU engine is behind the answer.

import http from 'node:http';

const PORT = Number(process.env.PORT || 8098);
const MOCK = process.env.B14_MOCK === '1';
const PROPS = {
  build_info: 'b14-rehearsal-mock (not llama.cpp, no GPU, no CUDA build)',
  model_path: MOCK
    ? '/mock/not-the-pin'
    : '/mock/not-the-pin (B14_MOCK unset — this is still a mock)',
  model_alias: 'B14-MOCK',
  mock: true,
};

let completions = 0;
const server = http.createServer((req, res) => {
  const url = String(req.url || '');
  const send = (code, body) => {
    const text = JSON.stringify(body);
    res.writeHead(code, {
      'content-type': 'application/json',
      'content-length': Buffer.byteLength(text),
    });
    res.end(text);
  };
  if (url === '/health' || url.startsWith('/health?')) return send(200, { status: 'ok', mock: MOCK });
  if (url === '/props' || url.startsWith('/props?')) return send(200, PROPS);
  if (url === '/v1/chat/completions' && req.method === 'POST') {
    let size = 0;
    req.on('data', (c) => (size += c.length));
    req.on('end', () => {
      completions += 1;
      send(200, {
        id: 'cmpl-mock',
        object: 'chat.completion',
        model: PROPS.model_alias,
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: '{"mock":true,"verdict":"rehearsal"}' },
            finish_reason: 'stop',
          },
        ],
        usage: { prompt_tokens: Math.ceil(size / 4), completion_tokens: 6, total_tokens: 6 },
      });
    });
    return undefined;
  }
  return send(404, { error: { message: `b14 mock has no route ${url}` } });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`vlm-mock: listening on ${PORT} (B14_MOCK=${process.env.B14_MOCK || 'unset'})`);
  console.log('vlm-mock: rehearsal only — its numbers are not the real tier');
});
setInterval(() => {}, 1 << 30).unref();
process.on('SIGTERM', () => server.close(() => process.exit(0)));
