#!/usr/bin/env node

/**
 * export-png.js — Converts an HTML course file into a full-page PNG infographic.
 *
 * Uses Puppeteer to render the HTML in headless Chrome, forces all animations
 * and chat messages to be visible, then captures a full-page screenshot
 * suitable for sharing as a long-form infographic on social media.
 *
 * Usage:
 *   node export-png.js <input.html> <output.png> [--width 1200]
 *
 * Examples:
 *   node export-png.js course.html infographic.png
 *   node export-png.js output/course.html output/infographic.png --width 800
 */

const path = require('path');
const fs = require('fs');

// ---------------------------------------------------------------------------
// Argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = argv.slice(2); // skip node + script path
  let inputFile = null;
  let outputFile = null;
  let width = 1200;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--width') {
      i++;
      if (i >= args.length) {
        console.error('Error: --width requires a value (e.g. --width 1200)');
        process.exit(1);
      }
      width = parseInt(args[i], 10);
      if (isNaN(width) || width < 100 || width > 10000) {
        console.error('Error: --width must be a number between 100 and 10000');
        process.exit(1);
      }
    } else if (args[i].startsWith('--')) {
      console.error(`Error: Unknown option "${args[i]}"`);
      printUsage();
      process.exit(1);
    } else if (!inputFile) {
      inputFile = args[i];
    } else if (!outputFile) {
      outputFile = args[i];
    } else {
      console.error('Error: Too many positional arguments');
      printUsage();
      process.exit(1);
    }
  }

  if (!inputFile || !outputFile) {
    printUsage();
    process.exit(1);
  }

  return { inputFile, outputFile, width };
}

function printUsage() {
  console.log(`
Usage: node export-png.js <input.html> <output.png> [--width 1200]

Arguments:
  input.html   Path to the HTML course file to render
  output.png   Path for the output PNG screenshot

Options:
  --width N    Viewport width in pixels (default: 1200, range: 100-10000)

Examples:
  node export-png.js course.html infographic.png
  node export-png.js output/course.html output/share.png --width 800
`.trim());
}

// ---------------------------------------------------------------------------
// Puppeteer loading (with helpful error on missing dependency)
// ---------------------------------------------------------------------------

function loadPuppeteer() {
  try {
    return require('puppeteer');
  } catch (err) {
    console.error(`
Error: Puppeteer is not installed.

Puppeteer is required to render HTML to PNG. Install it with:

  npm install puppeteer

This will also download a compatible Chromium binary (~170 MB).

If you already have Chrome/Chromium installed and want to use it instead:

  npm install puppeteer-core

Then set the PUPPETEER_EXECUTABLE_PATH environment variable to your
Chrome/Chromium path.
`.trim());
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Main export function
// ---------------------------------------------------------------------------

async function exportPng({ inputFile, outputFile, width }) {
  // Resolve to absolute paths
  const inputPath = path.resolve(inputFile);
  const outputPath = path.resolve(outputFile);

  // Validate input file exists
  if (!fs.existsSync(inputPath)) {
    console.error(`Error: Input file not found: ${inputPath}`);
    process.exit(1);
  }

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const puppeteer = loadPuppeteer();

  console.log(`Rendering: ${inputPath}`);
  console.log(`Viewport width: ${width}px`);

  let browser;
  try {
    // Launch headless Chrome
    const launchOptions = {
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
      ],
    };

    // Support custom Chrome path via environment variable
    if (process.env.PUPPETEER_EXECUTABLE_PATH) {
      launchOptions.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
    }

    browser = await puppeteer.launch(launchOptions);
    const page = await browser.newPage();

    // Set viewport
    await page.setViewport({
      width: width,
      height: 800, // initial height — fullPage screenshot ignores this
      deviceScaleFactor: 2, // retina quality
    });

    // Load the HTML file via file:// protocol
    const fileUrl = `file:///${inputPath.replace(/\\/g, '/')}`;
    await page.goto(fileUrl, {
      waitUntil: 'networkidle0',
      timeout: 30000,
    });

    // Wait for fonts to load
    await page.evaluate(() => {
      return document.fonts.ready;
    });

    // Force all .animate-in elements to be visible (bypass scroll triggers)
    await page.evaluate(() => {
      document.querySelectorAll('.animate-in').forEach((el) => {
        el.classList.add('visible');
      });
    });

    // Show all .chat-message elements (they may be hidden for sequential reveal)
    await page.evaluate(() => {
      document.querySelectorAll('.chat-message').forEach((el) => {
        el.style.display = 'flex';
        el.style.opacity = '1';
      });
    });

    // Wait for animations to settle
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Take full-page screenshot
    await page.screenshot({
      path: outputPath,
      fullPage: true,
      type: 'png',
    });

    // Report success with file size
    const stats = fs.statSync(outputPath);
    const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
    const sizeKB = (stats.size / 1024).toFixed(0);
    const sizeStr = stats.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;

    console.log(`\nSuccess! PNG exported to: ${outputPath}`);
    console.log(`File size: ${sizeStr}`);
  } catch (err) {
    console.error(`\nError during export: ${err.message}`);
    if (err.message.includes('Could not find expected browser')) {
      console.error(
        '\nHint: Puppeteer could not find a Chromium binary. Try running:\n  npx puppeteer browsers install chrome'
      );
    }
    process.exit(1);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const config = parseArgs(process.argv);
exportPng(config);
