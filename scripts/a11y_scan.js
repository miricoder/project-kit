// Accessibility scan for `pk qa a11y`. Driven by scripts/qa.py, which flattens each UI file to
// plain HTML first; this only needs a browser.
//
//   node a11y_scan.js <axe.min.js> <report.json> '[["ui/home.html", "/tmp/0.html"], ...]'
//
// Per file: axe-core WCAG 2.0/2.1 A and AA rules, every Tab stop checked for a visible focus
// indicator, and horizontal overflow at 320 CSS px (WCAG 1.4.10). qa.py turns the result
// into problems; keeping the judgement there means it is tested without a browser.
const fs = require('fs');
const { chromium } = require('playwright');

const [axePath, reportPath, filesJson] = process.argv.slice(2);
const AXE = fs.readFileSync(axePath, 'utf8');
const files = JSON.parse(filesJson);

(async () => {
  const browser = await chromium.launch();
  const results = [];
  for (const [name, htmlPath] of files) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    try {
      await page.setContent(fs.readFileSync(htmlPath, 'utf8'), { waitUntil: 'domcontentloaded' });
      await page.addScriptTag({ content: AXE });
      const violations = await page.evaluate(async () => {
        const r = await window.axe.run(document, {
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
        });
        return r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help,
          targets: v.nodes.map((n) => n.target.join(' ')) }));
      });

      const focusMissing = [];
      const seen = new Set();
      await page.evaluate(() => document.body.focus());
      for (let i = 0; i < 80; i++) {
        await page.keyboard.press('Tab');
        const stop = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const visible = (node) => {
            const cs = getComputedStyle(node);
            return (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
          };
          // A focus indicator may be drawn on the element or on a wrapper that styles :focus-within.
          let node = el, shown = false;
          for (let d = 0; node && d < 3 && !shown; d++, node = node.parentElement) shown = visible(node);
          const name = (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText)
            || el.innerText || el.value || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 60);
          const key = `${el.tagName}|${name}|${el.getBoundingClientRect().top}`;
          return { name, shown, key };
        });
        if (!stop || seen.has(stop.key)) break;
        seen.add(stop.key);
        if (!stop.shown) focusMissing.push(stop.name);
      }

      await page.setViewportSize({ width: 320, height: 844 });
      // Design frames are drawn at a fixed width; let them be fluid, as the real screen will be.
      await page.addStyleTag({ content: 'main,body>div:first-child{width:auto!important;max-width:100%!important;height:auto!important}' });
      const overflow320 = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      results.push({ file: name, violations, focusMissing, overflow320 });
    } catch (err) {
      results.push({ file: name, violations: [], focusMissing: [], overflow320: false, error: String(err.message || err) });
    } finally {
      await page.close();
    }
  }
  await browser.close();
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
})().catch((err) => { console.error(err); process.exit(1); });
