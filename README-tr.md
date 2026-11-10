# biletix-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/biletix-mcp

biletix.com için resmi olmayan **salt okunur** MCP sunucusu — Türkiye'nin en büyük bilet platformu (Ticketmaster'a ait): konser, tiyatro, festival, spor — öne çıkan/gündem etkinlikler, öne çıkanlarda anahtar kelime + şehir araması, tam etkinlik detayı (mekân, tarihler, en düşük fiyat, müsaitlik), kategoriye göre etkinlikler, mekânlar ve mekân başına yaklaşan etkinlikler.

> Mohammad Abbasi tarafından "Turkey MCP factory" (Sepehr tarzı hat) kapsamında geliştirildi. biletix.com ile bağlantısı yoktur.

## Yapay zekâ ajanları için

MCP istemci yapılandırmanıza ekleyin (stdio):

```json
{
  "mcpServers": {
    "biletix": {
      "command": "uvx",
      "args": ["biletix-mcp==0.1.0"]
    }
  }
}
```

Veya yerelde çalıştırın: `python -m biletix_mcp.server` (`mcp<2`, `curl-cffi` gerekir).

## Araçlar

| Araç | Açıklama |
|------|-------------|
| `biletix_trending` | Öne çıkan etkinlikler — `section`: "browse" ("Etkinliklere Göz Atın", 43 etkinlik), "starting_soon" ("24 Saat İçinde Başlayacaklar", 50 etkinlik), "all" (92 ayrı etkinlik); `limit` 1..50 |
| `biletix_search_events` | Ana sayfadaki öne çıkan etkinliklerde anahtar kelime araması — `query` ("Simge", "caz"), isteğe bağlı `city` ("istanbul", "ankara"); `limit` 1..50 |
| `biletix_get_event` | Tek bir etkinliğin tam detayı — `event_url` (trending/search araçlarının döndürdüğü URL); ad, açıklama, başlangıç/bitiş, durum, mekân (+ şehir, koordinat, mekân sayfası URL'si), en düşük fiyat (TRY), müsaitlik, görsel |
| `biletix_list_by_category` | Bir kategorideki öne çıkan etkinlikler — `category`: URL slug öneki, örn. "music"; ayrıca bugün ana sayfada bulunan kategorileri döner |
| `biletix_list_venues` | Öne çıkan etkinliklerin arkasındaki mekânlar (şehir + öne çıkan etkinlik sayısı); `limit` 1..50 |
| `biletix_venue_events` | Bir mekândaki yaklaşan etkinlikler — `venue_url` (`biletix_get_event` çıktısındaki `venue_url` alanı); `limit` 1..50 |

## Nasıl çalışır

biletix.com ana sayfasını (`/anasayfa/TURKIYE/tr`), etkinlik detay sayfalarını (`/etkinlik/<kod>/TURKIYE/tr/<slug>`), etkinlik grubu sayfalarını (`/etkinlik-grup/<id>/...`) ve mekân sayfalarını (`/mekan/<kod>/...`) tamamen sunucu taraflı gösterir — giriş, API anahtarı ve çerez gerekmez. Ana sayfanın kendisi (`/`) yalnızca 1,1 KB'lık bir JS yönlendiricidir (`redirector.js` → `/anasayfa/TURKIYE/tr`). Ana sayfada iki bölüm sunucu taraflı gösterilir: "Etkinliklere Göz Atın" (43 kart) ve "24 Saat İçinde Başlayacaklar" (50 kart); "Popüler Etkinlikler" ve "Biletix'te Yeni Satışta" yalnızca istemci taraflı yüklenir. Etkinlik kartları schema.org mikroverisi taşır (başlık, başlangıç/bitiş, mekân + şehir, en düşük fiyat TRY, slug'da kategori + tarih + şehir, örn. `music-aura-16-11-2026-istanbul`); grup/tur kartları (`/etkinlik-grup/...`, mekân "Çeşitli Mekanlar") aynı biçimdedir. Detay sayfalarında tam Event JSON-LD bloğu vardır (açıklama, adresli + koordinatlı mekân, fiyat/müsaitlik). Fiyatlar görünen metinde Türk biçimindedir ("1.995₺" → 1995,0; "3.171,25₺" → 3171,25). `/search` ve `/category` sayfaları Angular kabuğudur ve `/api/v1/searchquery/searchSuggestion` uç noktası doğrudan çağrılarda 404 sayfasına yönlendirir; bu yüzden anahtar kelime araması ana sayfanın öne çıkanlarıyla sınırlıdır (derleme anında 92 ayrı etkinlik). Arama sayfasında Queue-it bekleme odası betikleri yüklenir ama SSR çekmeleri engellemez. Aktarım Chrome TLS taklidi kullanır (`curl-cffi`, `chrome120`); istekler ~0,8 sn arayla; her şey salt okunurdur.

## Kurulum

```bash
uvx biletix-mcp==0.1.0        # doğrudan çalıştır (uv gerekir)
# veya
pip install biletix-mcp==0.1.0
biletix-mcp    # MCP sunucusunu stdio üzerinde başlatır
```

## Testler

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Çevrimdışı testler kaydedilmiş gerçek sayfalarla çalışır (2026-11-07'de çekildi); canlı testler biletix.com'a bağlanır. 24/24 yeşil (15 çevrimdışı + 9 canlı) + MCP stdio duman testi.

## Yol haritası

- Tam katalog araması (sitenin istemci taraflı arama API'si veya etkinlik URL'lerinin site haritası gerekir)
- Etkinlik başına bilet kategorileri / koltuk planı fiyatları (şu an yalnızca "en düşük" fiyat)
- Sanatçı sayfaları (`/etkinlik-grup/...` zaten tur tarihlerini listeler)

## Lisans

MIT — bkz. [LICENSE](LICENSE).
