() => {
  const NUM = '(\\d{1,3}(?:[\\s\\u00a0.]\\d{3})*[.,]\\d{1,2}|\\d+[.,]\\d{1,2})';
  const PRICE = new RegExp('(?:PLN\\s?' + NUM + ')|(?:' + NUM + '\\s?(?:zł|PLN))', 'i');
  const toNum = s => { s = s.replace(/[\s\u00a0]/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); return parseFloat(s); };
  const priceIn = el => { const m = PRICE.exec(el.innerText || ''); return m ? toNum(m[1] || m[2]) : null; };
  const out = [], seen = new Set();
  const push = (title, price, url) => { if (!url || seen.has(url) || !(price > 0)) return; seen.add(url); out.push({title, price, url}); };
  for (const ar of document.querySelectorAll('article')) {
    const h = ar.querySelector('h2, h3');
    const title = ((h && h.innerText) || '').trim().replace(/\s+/g, ' ');
    if (!/sorvella/i.test(title)) continue;
    const links = [...ar.querySelectorAll('a[href]')].map(a => a.href);
    push(title, priceIn(ar), links.find(u => !/\/events\//.test(u)) || links[0]);
  }
  if (!out.length) {
    for (const a of document.querySelectorAll('a[href]')) {
      const title = (a.getAttribute('title') || a.innerText || '').trim().replace(/\s+/g, ' ');
      if (title.length < 8 || !/sorvella/i.test(title)) continue;
      let node = a, price = null;
      for (let i = 0; i < 6 && !price; i++) { node = node.parentElement; if (!node) break; price = priceIn(node); }
      push(title, price, a.href);
    }
  }
  return out;
}
