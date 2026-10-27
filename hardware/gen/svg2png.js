// Rasterise SVG files with the preinstalled Chromium: node svg2png.js in.svg out.png [widthPx]
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [, , inp, out, w] = process.argv;
  const svg = fs.readFileSync(inp, 'utf8');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: parseInt(w || '1800'), height: 200 } });
  await page.setContent(`<html><body style="margin:0;background:#fff"><div id=w style="width:100%">${svg}</div></body></html>`);
  await page.evaluate(() => { const s = document.querySelector('svg'); s.setAttribute('width', '100%'); s.removeAttribute('height'); });
  const el = await page.$('svg');
  await el.screenshot({ path: out });
  await browser.close();
})();
