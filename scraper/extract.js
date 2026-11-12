() => {
  const NUM = '(\\d{1,3}(?:[\\s\\u00a0.]\\d{3})*[.,]\\d{1,2}|\\d+[.,]\\d{1,2})';
  // "119,90 zł" | "PLN 87.89" | Hebe style: "75" + small "00" + "złoty"
  const PRICE = new RegExp('(?:PLN\\s?' + NUM + ')|(?:' + NUM + '\\s?(?:zł|PLN))|(?:(?<![\\d.,])(\\d{1,4})\\s+(\\d{2})\\s*(?:zł|złoty|zloty))', 'i');
  const toNum = s => { s = s.replace(/[\s\u00a0]/g, ''); if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.'); return parseFloat(s); };
  const fromMatch = m => !m ? null : m[1] ? toNum(m[1]) : m[2] ? toNum(m[2]) : m[3] ? parseFloat(m[3] + '.' + m[4]) : null;
  // Hebe prints "75" + small "00" + "złoty" as separate elements, so the text may have no separator at all.
  const supPrice = el => {
    for (const x of el.querySelectorAll('sup, sub, [class*="decimal"], [class*="grosz"], [class*="fraction"], [class*="cents"]')) {
      const dec = (x.textContent || '').trim();
      if (!/^\d{2}$/.test(dec)) continue;
      let prev = x.previousSibling;
      while (prev && !(prev.textContent || '').trim()) prev = prev.previousSibling;
      let whole = prev ? (prev.textContent || '').trim() : '';
      if (!/^\d{1,4}$/.test(whole)) { const m = /(\d{1,4})\s*$/.exec(whole); whole = m ? m[1] : ''; }
      if (/^\d{1,4}$/.test(whole)) return parseFloat(whole + '.' + dec);
    }
    return null;
  };
  const priceIn = el => { const v = fromMatch(PRICE.exec(el.innerText || '')); return v != null ? v : supPrice(el); };
  const out = [], seen = new Set();
  // Who sells it, as far as the listing shows: Allegro seller link, "Hebe Partner sells", "in 8 stores" (Ceneo).
  const sellerOf = card => {
    if (!card) return null;
    const a = card.querySelector('a[href*="/uzytkownik/"], a[href*="/sklep/"]');
    if (a && (a.textContent || '').trim()) return a.textContent.trim().replace(/\s+/g, ' ').slice(0, 60);
    const lines = (card.innerText || '').split('\n').map(x => x.replace(/\s+/g, ' ').trim()).filter(Boolean);
    const l = lines.find(x => x.length < 70 && /(sprzedaj|sprzedawc|sold by|seller|sells|selling)/i.test(x));
    if (l) return l;
    const m = /(?:\bw\s+|\bin\s+)?(\d+)\s+(?:sklep\w*|stores?|shops?)/i.exec(card.innerText || '');
    return m ? 'in ' + m[1] + ' stores' : null;
  };
  const push = (title, price, url, seller) => { if (!url || seen.has(url) || !(price > 0)) return; seen.add(url); const o = {title, price, url}; if (seller) o.seller = seller; out.push(o); };
  // Titles without a size ("Sorvella S-530"): add the line under the title and the first "N ml" of the card.
  const enrich = (title, card) => {
    if (/\d\s?ml/i.test(title) || !card) return title;
    const text = card.innerText || '';
    const lines = text.split('\n').map(x => x.replace(/\s+/g, ' ').trim()).filter(Boolean);
    const i = lines.findIndex(l => l.toLowerCase() === title.toLowerCase());
    let sub = i >= 0 ? lines[i + 1] || '' : '';
    if (!sub || PRICE.test(sub) || sub.length > 90) sub = '';
    let t = sub && !title.toLowerCase().includes(sub.toLowerCase()) ? title + ' ' + sub : title;
    if (!/\d\s?ml/i.test(t)) { const m = /(\d{1,4})\s?ml/i.exec(text); if (m) t += ' ' + m[1] + ' ml'; }
    return t;
  };
  for (const ar of document.querySelectorAll('article')) {
    const h = ar.querySelector('h2, h3');
    const title = ((h && h.innerText) || '').trim().replace(/\s+/g, ' ');
    if (!/sorvella/i.test(title)) continue;
    const links = [...ar.querySelectorAll('a[href]')].map(a => a.href);
    push(enrich(title, ar), priceIn(ar), links.find(u => !/\/events\//.test(u)) || links[0], sellerOf(ar));
  }
  if (!out.length) {
    for (const a of document.querySelectorAll('a[href]')) {
      const title = (a.getAttribute('title') || a.innerText || '').trim().replace(/\s+/g, ' ');
      if (title.length < 8 || !/sorvella/i.test(title)) continue;
      let node = a, price = null, card = null;
      for (let i = 0; i < 6; i++) { node = node.parentElement; if (!node) break; price = priceIn(node); if (price) { card = node; break; } }
      push(enrich(title, card), price, a.href, sellerOf(card));
    }
  }
  if (!out.length) {
    // Third strategy: shops that show the brand in its own box, separate from the product name.
    const PURE = new RegExp('^\\s*(?:od\\s+)?(?:PLN\\s?' + NUM + '|' + NUM + '\\s?(?:zł|PLN))\\s*$', 'i');
    const cands = [...document.querySelectorAll('li, article, div')].filter(el => {
      const t = el.innerText || '';
      return t.length > 20 && t.length < 700 && /sorvella/i.test(t) && PRICE.test(t) && el.querySelector('a[href]');
    });
    const set = new Set(cands);
    for (const el of cands.filter(c => ![...c.querySelectorAll('*')].some(x => set.has(x)))) {
      const lines = (el.innerText || '').split('\n').map(x => x.trim()).filter(Boolean);
      let title = lines.filter(l => !PRICE.test(l) && l.length > 8).sort((a, b) => b.length - a.length)[0] || '';
      if (!/sorvella/i.test(title)) title = 'Sorvella ' + title;
      const pure = [...el.querySelectorAll('*')].filter(x => !x.children.length && PURE.test(x.innerText || '') && !/\//.test(x.innerText || ''))
        .map(x => fromMatch(PRICE.exec(x.innerText))).filter(n => n > 0);
      const link = [...el.querySelectorAll('a[href]')].map(a => a.href).find(u => u && !u.endsWith('#') && !/^javascript:/.test(u));
      push(title.replace(/\s+/g, ' '), pure.length ? Math.min(...pure) : priceIn(el), link, sellerOf(el));
    }
  }
  return out;
}
