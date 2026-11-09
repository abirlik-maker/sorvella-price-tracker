# Sorvella fiyat karşılaştırma

sorvellaperfume.pl ürünlerini Allegro, Ceneo, Notino, Douglas, Sephora, Rossmann, Hebe ve Super-Pharm'da arar,
fiyatları günlük kaydeder, `docs/` altındaki dashboard'da gösterir.

## Kurulum (10 dakika)
1. Bu klasörü yeni bir GitHub reposuna yükle.
2. **Settings → Pages**: Source = `main`, klasör = `/docs`. Dashboard adresi burada çıkar.
3. **Settings → Secrets and variables → Actions**: `ALLEGRO_CLIENT_ID` ve `ALLEGRO_CLIENT_SECRET` ekle
   (https://apps.developer.allegro.pl adresinden ücretsiz uygulama kaydı). Bunlar olmadan Allegro "Off" görünür.
4. **Actions → daily-prices → Run workflow** ile ilk çalıştırmayı elle başlat. Sonra her gün 06:00 UTC'de kendiliğinden çalışır.

## Dosyalar
- `scraper/` Python scriptleri. `python -m scraper.run` yerelde de çalışır.
- `docs/index.html` dashboard. `docs/data/` günlük JSON verisi (workflow commit'ler).
- `overrides.json` hatalı eşleşen ilanı `ignore_urls` ile dışla, ürün türü hariç tut (`exclude_types`).
- `demo.html` örnek veriyle tek dosyalık önizleme (çift tıkla aç). `python make_demo.py` yeniden üretir.

## Bilinen sınırlar
- Sorvella kendi markanız. Rakip sitede eşleşme ancak aynı ürün orada satılıyorsa çıkar. Eşleşme yoksa "No match" yazar.
- Allegro resmi API ile çalışır. Diğer kanallar düz HTML okur ve GitHub sunucularından test edilmedi.
  Bot korumalı ya da JS ile yüklenen siteler dashboard'da "Blocked" / "Unreadable" görünür.
  Bu durumda ilgili kanal için Playwright adaptörü eklenir.
