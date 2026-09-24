#!/usr/bin/env node

// Serve this preview over localhost so the browser can fetch its sibling JSON.
const { createServer } = require('node:http');
const { readFile } = require('node:fs/promises');
const { join, resolve } = require('node:path');
const { spawn } = require('node:child_process');

const previewDir = process.argv[2] ? resolve(process.argv[2]) : __dirname;

const files = {
  '/': ['wireframe_preview.html', 'text/html; charset=utf-8'],
  '/wireframe_preview.html': ['wireframe_preview.html', 'text/html; charset=utf-8'],
  '/wireframe_preview.json': ['wireframe_preview.json', 'application/json; charset=utf-8'],
};

const server = createServer(async (request, response) => {
  const file = files[request.url];
  if (!file) {
    response.writeHead(404).end('Not found');
    return;
  }

  try {
    const body = await readFile(join(previewDir, file[0]));
    response.writeHead(200, { 'Content-Type': file[1], 'Cache-Control': 'no-store' }).end(body);
  } catch (error) {
    console.error(`Could not read ${file[0]}:`, error);
    response.writeHead(500).end('Could not load preview');
  }
});

server.listen(0, '127.0.0.1', () => {
  const url = `http://127.0.0.1:${server.address().port}/wireframe_preview.html`;
  console.log(`Preview: ${url}\nServing: ${previewDir}\nReload the page after editing wireframe_preview.json. Press Ctrl+C to stop.`);

  if (process.env.PREVIEW_NO_OPEN === '1') return;

  const command = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'cmd' : 'xdg-open';
  const args = process.platform === 'win32' ? ['/c', 'start', '', url] : [url];
  const browser = spawn(command, args, { stdio: 'ignore' });
  browser.on('error', () => console.log(`Open ${url} in your browser.`));
});
