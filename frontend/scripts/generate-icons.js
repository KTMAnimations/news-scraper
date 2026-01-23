#!/usr/bin/env node
/**
 * Icon generation script for Micro-Alpha PWA
 *
 * This script generates PNG icons from the SVG source.
 * Requires: sharp (npm install sharp)
 *
 * Run: node scripts/generate-icons.js
 */

const fs = require('fs');
const path = require('path');

// Check if sharp is available
let sharp;
try {
  sharp = require('sharp');
} catch (e) {
  console.log('Sharp not installed. To generate PNG icons:');
  console.log('  1. npm install sharp');
  console.log('  2. node scripts/generate-icons.js');
  console.log('\nAlternatively, use an online tool to convert the SVG at:');
  console.log('  public/icons/icon.svg');
  process.exit(0);
}

const ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512];
const MASKABLE_SIZES = [192, 512];

const iconsDir = path.join(__dirname, '..', 'public', 'icons');
const svgPath = path.join(iconsDir, 'icon.svg');

async function generateIcons() {
  console.log('Generating PWA icons...');

  const svgBuffer = fs.readFileSync(svgPath);

  // Generate standard icons
  for (const size of ICON_SIZES) {
    const outputPath = path.join(iconsDir, `icon-${size}x${size}.png`);
    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(outputPath);
    console.log(`  Created: icon-${size}x${size}.png`);
  }

  // Generate maskable icons (with extra padding)
  for (const size of MASKABLE_SIZES) {
    const outputPath = path.join(iconsDir, `icon-maskable-${size}x${size}.png`);
    // Maskable icons should have 10% padding (safe zone)
    const innerSize = Math.floor(size * 0.8);
    await sharp(svgBuffer)
      .resize(innerSize, innerSize)
      .extend({
        top: Math.floor((size - innerSize) / 2),
        bottom: Math.ceil((size - innerSize) / 2),
        left: Math.floor((size - innerSize) / 2),
        right: Math.ceil((size - innerSize) / 2),
        background: { r: 10, g: 10, b: 11, alpha: 1 }
      })
      .png()
      .toFile(outputPath);
    console.log(`  Created: icon-maskable-${size}x${size}.png`);
  }

  // Generate Apple touch icon
  const appleTouchPath = path.join(iconsDir, 'apple-touch-icon.png');
  await sharp(svgBuffer)
    .resize(180, 180)
    .png()
    .toFile(appleTouchPath);
  console.log('  Created: apple-touch-icon.png');

  // Generate favicon
  const faviconPath = path.join(__dirname, '..', 'public', 'favicon.ico');
  await sharp(svgBuffer)
    .resize(32, 32)
    .png()
    .toFile(faviconPath.replace('.ico', '.png'));
  console.log('  Created: favicon.png');

  console.log('\nIcon generation complete!');
}

generateIcons().catch(console.error);
