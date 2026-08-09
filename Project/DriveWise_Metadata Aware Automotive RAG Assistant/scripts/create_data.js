#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const brand = argv[0] || 'BrandName';
const brochureSrc = argv[1];

const projectRoot = path.resolve(__dirname, '..');
const dataDir = path.join(projectRoot, 'data');
const brandDir = path.join(dataDir, brand);

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

ensureDir(brandDir);

if (brochureSrc) {
  const src = path.resolve(brochureSrc);
  if (!fs.existsSync(src)) {
    console.error('Source brochure not found:', src);
    process.exit(2);
  }
  const dest = path.join(brandDir, 'brochure.pdf');
  fs.copyFileSync(src, dest);
  console.log('Copied brochure to', dest);
  process.exit(0);
}

// Create a small placeholder "PDF" file (text placeholder) so the folder is present
const placeholderPath = path.join(brandDir, 'brochure.pdf');
const placeholderText = `DriveWise Brochure Placeholder\n\nBrand: ${brand}\n\nReplace this file with the real brochure PDF.`;
fs.writeFileSync(placeholderPath, placeholderText, { encoding: 'utf8' });
console.log('Created placeholder brochure at', placeholderPath);
