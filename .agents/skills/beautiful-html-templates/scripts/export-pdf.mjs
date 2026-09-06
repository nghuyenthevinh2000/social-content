#!/usr/bin/env node
/**
 * Universal PDF Exporter for HTML Presentation Decks
 *
 * Supports:
 *  1. <deck-stage> web-component presentations (single-pass 16:9 vector print)
 *  2. Interactive single-screen decks (automated key-stepping through ArrowRight + pdfunite)
 *
 * Usage:
 *   node scripts/export-pdf.mjs [path/to/deck.html] [output.pdf] [--slides N] [--delay ms]
 *
 * Requirements:
 *   - macOS with Google Chrome installed (/Applications/Google Chrome.app)
 *   - pdfunite (/opt/homebrew/bin/pdfunite) or ghostscript (gs)
 */

import { spawn, execSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, unlinkSync, mkdtempSync, rmSync } from 'node:fs';
import { join, resolve, dirname, basename, extname } from 'node:path';
import { tmpdir } from 'node:os';

const CHROME_PATH = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

if (!existsSync(CHROME_PATH)) {
  console.error(`❌ Google Chrome not found at: ${CHROME_PATH}`);
  console.error('Please install Google Chrome or set CHROME_BIN.');
  process.exit(1);
}

// Parse CLI Arguments
const args = process.argv.slice(2);
let inputPath = null;
let outputPath = null;
let forcedSlides = null;
let delayMs = 500;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--slides' || args[i] === '-s') {
    forcedSlides = parseInt(args[++i], 10);
  } else if (args[i] === '--delay' || args[i] === '-d') {
    delayMs = parseInt(args[++i], 10);
  } else if (!inputPath) {
    inputPath = args[i];
  } else if (!outputPath) {
    outputPath = args[i];
  }
}

// Default input path
if (!inputPath) {
  if (existsSync('template.html')) inputPath = 'template.html';
  else if (existsSync('index.html')) inputPath = 'index.html';
  else if (existsSync('slides.html')) inputPath = 'slides.html';
  else {
    console.error('❌ No input HTML file specified and no default template.html found.');
    console.error('Usage: node export-pdf.mjs [path/to/deck.html] [output.pdf]');
    process.exit(1);
  }
}

const resolvedInput = resolve(inputPath);
if (!existsSync(resolvedInput)) {
  console.error(`❌ Input file not found: ${resolvedInput}`);
  process.exit(1);
}

if (!outputPath) {
  const dir = dirname(resolvedInput);
  const base = basename(resolvedInput, extname(resolvedInput));
  outputPath = join(dir, `${base}.pdf`);
}
const resolvedOutput = resolve(outputPath);

console.log(`\n📄 Exporting Deck to PDF`);
console.log(`   Input:  ${resolvedInput}`);
console.log(`   Output: ${resolvedOutput}\n`);

// Launch Headless Chrome with CDP
const chromeProc = spawn(CHROME_PATH, [
  '--headless=new',
  '--remote-debugging-port=0',
  '--disable-gpu',
  '--window-size=1920,1080',
  'about:blank'
], { stdio: ['ignore', 'pipe', 'pipe'] });

let wsUrl = null;
chromeProc.stderr.on('data', (chunk) => {
  const match = chunk.toString().match(/DevTools listening on (ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[^\s]+)/);
  if (match) {
    wsUrl = match[1];
    startExport().catch((err) => {
      console.error('❌ Export failed:', err);
      cleanup();
      process.exit(1);
    });
  }
});

function cleanup() {
  try { chromeProc.kill('SIGTERM'); } catch {}
}

process.on('SIGINT', () => { cleanup(); process.exit(1); });
process.on('SIGTERM', () => { cleanup(); process.exit(1); });

async function startExport() {
  const ws = new WebSocket(wsUrl);
  let id = 1;
  const pending = new Map();

  ws.onmessage = (e) => {
    const res = JSON.parse(e.data);
    if (res.id && pending.has(res.id)) {
      pending.get(res.id)(res);
      pending.delete(res.id);
    }
  };

  function send(method, params = {}) {
    return new Promise((res) => {
      const msgId = id++;
      pending.set(msgId, res);
      ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }

  await new Promise((r) => (ws.onopen = r));

  // Open Target File
  const fileUrl = `file://${resolvedInput}`;
  const { result: { targetId } } = await send('Target.createTarget', { url: fileUrl });
  const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });

  function sendSession(method, params = {}) {
    return new Promise((res) => {
      const msgId = id++;
      pending.set(msgId, res);
      ws.send(JSON.stringify({ id: msgId, sessionId, method, params }));
    });
  }

  await sendSession('Page.enable');
  await sendSession('Runtime.enable');
  
  // Wait for fonts & initial layout to stabilize
  await new Promise((r) => setTimeout(r, 1200));

  // Detect slide architecture
  const detectScript = `(() => {
    const hasDeckStage = !!document.querySelector('deck-stage');
    if (hasDeckStage) {
      const count = document.querySelectorAll('deck-stage > section').length;
      return { type: 'deck-stage', count };
    }
    if (typeof totalSlides !== 'undefined' && typeof totalSlides === 'number' && totalSlides > 0) {
      return { type: 'interactive', count: totalSlides };
    }
    if (typeof total !== 'undefined' && typeof total === 'number' && total > 0) {
      return { type: 'interactive', count: total };
    }
    if (typeof slides !== 'undefined' && Array.isArray(slides) && slides.length > 0) {
      return { type: 'interactive', count: slides.length };
    }
    const slideEls = document.querySelectorAll('.slide, section.slide, main > section');
    if (slideEls.length > 0) {
      return { type: 'interactive', count: slideEls.length };
    }
    const allSections = document.querySelectorAll('section');
    return { type: 'interactive', count: allSections.length || 1 };
  })()`;

  const { result: { result: evalRes } } = await sendSession('Runtime.evaluate', {
    expression: detectScript,
    returnByValue: true
  });

  const detection = evalRes.value || { type: 'interactive', count: 1 };
  const engineType = detection.type;
  const slideCount = forcedSlides || detection.count;

  console.log(`🔍 Detected Engine: [${engineType}] | Total Slides: ${slideCount}`);

  if (engineType === 'deck-stage') {
    // Single-pass print export
    console.log('⚡ Exporting all slides in single pass via <deck-stage> print engine...');
    const pdfRes = await sendSession('Page.printToPDF', {
      landscape: false,
      printBackground: true,
      paperWidth: 16,
      paperHeight: 9,
      preferCSSPageSize: true
    });

    writeFileSync(resolvedOutput, Buffer.from(pdfRes.result.data, 'base64'));
  } else {
    // Interactive slide stepping
    console.log(`⏩ Stepping through ${slideCount} slides with keyboard navigation...`);
    const tempDir = mkdtempSync(join(tmpdir(), 'deck-export-'));
    const tempPdfs = [];

    for (let i = 0; i < slideCount; i++) {
      console.log(`   📸 Capturing slide ${i + 1}/${slideCount}...`);

      const pdfRes = await sendSession('Page.printToPDF', {
        landscape: false,
        printBackground: true,
        paperWidth: 16,
        paperHeight: 9,
        pageRanges: '1'
      });

      const tempFile = join(tempDir, `slide_${String(i).padStart(3, '0')}.pdf`);
      writeFileSync(tempFile, Buffer.from(pdfRes.result.data, 'base64'));
      tempPdfs.push(tempFile);

      // Advance to next slide if not on the last one
      if (i < slideCount - 1) {
        await sendSession('Input.dispatchKeyEvent', {
          type: 'keyDown',
          key: 'ArrowRight',
          code: 'ArrowRight',
          windowsVirtualKeyCode: 39
        });
        await sendSession('Input.dispatchKeyEvent', {
          type: 'keyUp',
          key: 'ArrowRight',
          code: 'ArrowRight',
          windowsVirtualKeyCode: 39
        });
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }

    // Merge individual PDFs
    console.log('🔗 Merging slides into master presentation...');
    const hasPdfunite = existsSync('/opt/homebrew/bin/pdfunite');
    if (hasPdfunite) {
      execSync(`/opt/homebrew/bin/pdfunite ${tempPdfs.map(f => `"${f}"`).join(' ')} "${resolvedOutput}"`);
    } else {
      execSync(`gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile="${resolvedOutput}" ${tempPdfs.map(f => `"${f}"`).join(' ')}`);
    }

    rmSync(tempDir, { recursive: true, force: true });
  }

  await send('Browser.close');
  ws.close();
  cleanup();

  console.log(`\n✅ Successfully exported presentation: ${resolvedOutput}`);
  try {
    const info = execSync(`pdfinfo "${resolvedOutput}"`, { encoding: 'utf8' });
    const pagesMatch = info.match(/Pages:\s+(\d+)/);
    const sizeMatch = info.match(/Page size:\s+([^\n]+)/);
    console.log(`   Pages:     ${pagesMatch ? pagesMatch[1] : 'N/A'}`);
    console.log(`   Page Size: ${sizeMatch ? sizeMatch[1] : '16:9'}\n`);
  } catch {}

  process.exit(0);
}
