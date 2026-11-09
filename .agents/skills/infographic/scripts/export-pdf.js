#!/usr/bin/env node
/**
 * High-Resolution Vector PDF Export Utility for Infographics
 *
 * Generates exact-dimension, single-page vector PDFs of HTML infographics/slides,
 * with web fonts preloading, zero margins, and CSS print rule preservation.
 *
 * Usage:
 *   node export-pdf.js <input-html-or-url> <output-pdf-path> [options]
 *
 * Options:
 *   --width <number>      Viewport & PDF width in pixels (default: 720)
 *   --height <number>     Viewport & PDF height in pixels (default: 1280)
 *   --timeout <number>    Wait time in ms after load (default: 1000)
 *   --margin <string>     Page margin (default: '0px')
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('Usage: node export-pdf.js <input-html-or-url> <output-pdf-path> [--width 720] [--height 1280] [--timeout 1000] [--margin 0px]');
  process.exit(1);
}

let inputUrl = args[0];
let outputPath = path.resolve(args[1]);

if (!inputUrl.startsWith('http://') && !inputUrl.startsWith('https://') && !inputUrl.startsWith('file://')) {
  inputUrl = 'file://' + path.resolve(inputUrl);
}

let width = 720;
let height = 1280;
let timeout = 1000;
let margin = '0px';

for (let i = 2; i < args.length; i++) {
  if (args[i] === '--width' && args[i + 1]) width = parseInt(args[++i], 10);
  else if (args[i] === '--height' && args[i + 1]) height = parseInt(args[++i], 10);
  else if (args[i] === '--timeout' && args[i + 1]) timeout = parseInt(args[++i], 10);
  else if (args[i] === '--margin' && args[i + 1]) margin = args[++i];
}

// Dynamically resolve Playwright from local, global, or npx caches
function loadPlaywright() {
  try {
    return require('playwright');
  } catch (e) {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const npxDir = path.join(homeDir, '.npm', '_npx');
    if (fs.existsSync(npxDir)) {
      try {
        const findCmd = `find "${npxDir}" -name "playwright" -type d 2>/dev/null | grep "/node_modules/playwright$" | head -n 1`;
        const found = execSync(findCmd, { encoding: 'utf-8' }).trim();
        if (found) return require(found);
      } catch (err) {}
    }
    try {
      const globalRoot = execSync('npm root -g', { encoding: 'utf-8' }).trim();
      const globalPlaywright = path.join(globalRoot, 'playwright');
      if (fs.existsSync(globalPlaywright)) return require(globalPlaywright);
    } catch (err) {}
    throw new Error('Playwright not found. Run: npx playwright install chromium');
  }
}

(async () => {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();

  const page = await browser.newPage({
    viewport: { width, height }
  });

  console.log(`Navigating to ${inputUrl}...`);
  await page.goto(inputUrl, { waitUntil: 'networkidle' });

  // Ensure all web fonts are loaded
  try {
    await page.evaluate(() => document.fonts.ready);
  } catch (err) {}

  if (timeout > 0) {
    await page.waitForTimeout(timeout);
  }

  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  console.log(`Exporting vector PDF (${width}x${height}px, margin: ${margin})...`);
  await page.pdf({
    path: outputPath,
    width: `${width}px`,
    height: `${height}px`,
    printBackground: true,
    preferCSSPageSize: true,
    margin: {
      top: margin,
      right: margin,
      bottom: margin,
      left: margin
    }
  });

  await browser.close();

  const stats = fs.statSync(outputPath);
  console.log(`✓ Vector PDF successfully saved to: ${outputPath} [${(stats.size / 1024).toFixed(1)} KB]`);
})().catch(err => {
  console.error('Error exporting PDF:', err);
  process.exit(1);
});
