#!/usr/bin/env node
/**
 * High-Resolution Retina Screenshot Utility for one-pager-html
 * 
 * Captures pixel-perfect 2x (or Nx) Retina screenshots of HTML one-pagers,
 * ensuring sharp typography, crisp borders, and zero blurriness on high-DPI displays.
 * 
 * Usage:
 *   node screenshot-retina.js <input-url-or-path> <output-png-path> [options]
 * 
 * Options:
 *   --scale <number>      Device scale factor (default: 2 for Retina)
 *   --width <number>      Viewport width in pixels (default: 900 for A4)
 *   --height <number>     Viewport height in pixels (default: 1273 for A4)
 *   --timeout <number>    Wait time in ms after load (default: 2000)
 *   --full-page           Capture full scrollable page instead of fixed viewport
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Parse CLI arguments
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('Usage: node screenshot-retina.js <input-html-or-url> <output-png-path> [--scale 2] [--width 900] [--height 1273]');
  process.exit(1);
}

let inputUrl = args[0];
let outputPath = path.resolve(args[1]);

// Convert local file paths to file:// URLs
if (!inputUrl.startsWith('http://') && !inputUrl.startsWith('https://') && !inputUrl.startsWith('file://')) {
  inputUrl = 'file://' + path.resolve(inputUrl);
}

let scale = 2;
let width = 900;
let height = 1273;
let timeout = 2000;
let fullPage = false;

for (let i = 2; i < args.length; i++) {
  if (args[i] === '--scale' && args[i + 1]) scale = parseFloat(args[++i]);
  else if (args[i] === '--width' && args[i + 1]) width = parseInt(args[++i], 10);
  else if (args[i] === '--height' && args[i + 1]) height = parseInt(args[++i], 10);
  else if (args[i] === '--timeout' && args[i + 1]) timeout = parseInt(args[++i], 10);
  else if (args[i] === '--full-page') fullPage = true;
}

// Dynamically resolve Playwright from local, global, or npx caches
function loadPlaywright() {
  try {
    return require('playwright');
  } catch (e) {
    // Search ~/.npm/_npx
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const npxDir = path.join(homeDir, '.npm', '_npx');
    if (fs.existsSync(npxDir)) {
      try {
        const findCmd = `find "${npxDir}" -name "playwright" -type d 2>/dev/null | grep "/node_modules/playwright$" | head -n 1`;
        const found = execSync(findCmd, { encoding: 'utf-8' }).trim();
        if (found) {
          return require(found);
        }
      } catch (err) {}
    }
    // Search global npm root
    try {
      const globalRoot = execSync('npm root -g', { encoding: 'utf-8' }).trim();
      const globalPlaywright = path.join(globalRoot, 'playwright');
      if (fs.existsSync(globalPlaywright)) {
        return require(globalPlaywright);
      }
    } catch (err) {}
    throw new Error('Playwright not found. Run: npx playwright install chromium');
  }
}

(async () => {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: scale // Upscale 2x (1800x2546px for standard A4)
  });

  const page = await context.newPage();
  console.log(`Navigating to ${inputUrl}...`);
  await page.goto(inputUrl, { waitUntil: 'networkidle' });

  // Ensure all web fonts are fully rasterized
  try {
    await page.evaluate(() => document.fonts.ready);
  } catch (err) {}

  if (timeout > 0) {
    await page.waitForTimeout(timeout);
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  console.log(`Capturing screenshot (scale: ${scale}x, resolution: ${width * scale}x${height * scale}px)...`);
  await page.screenshot({
    path: outputPath,
    fullPage: fullPage
  });

  await browser.close();
  console.log(`✓ Screenshot successfully saved to: ${outputPath}`);
})().catch(err => {
  console.error('Error capturing screenshot:', err);
  process.exit(1);
});
