---
name: supervisor-review
description: Bir KONUYU (karar, plan, tasarım, doküman, strateji, kod-alanı — diff DEĞİL) yargı için değerlendirir. Konuyu tek eksende örtüşmeyen (MECE) dilimlere böler, her dilimi bağımsız Opus'larla paralel değerlendirir (yüksek-stakes 2x), iki Opus ayrışırsa KORUR (ayrışma = sinyal, ortalanmaz), tek karar artefaktına (go / koşullu / no-go / eksik-bilgi) sentezler. adversarial-review'in yargı tümleyeni — o çökertir, bu korur. Yüksek-stakes, çok-yönlü kararlar için. Mimari — ../../docs/architecture.md.
disable-model-invocation: true
allowed-tools: Bash(git:*), Read, Grep
---

# /supervisor-review — ekseni seç, paralel değerlendir, yargıyı sentezle

`/adversarial-review`'in yargı/titizlik tümleyeni. O bir DIFF'te bug avlar; bu bir KONUYU (karar, plan, tasarım, doküman, strateji, kod-alanı) yargı için değerlendirir. İnce giriş budur; orkestrasyon `workflows/supervisor-review.js`'de (deterministik fan-out + paralel değerlendirme).

Fark şu — adversarial-review anlaşmazlığı ÇÖKERTİR (çoğunluk oyu sahte-pozitifi öldürür); supervisor-review anlaşmazlığı KORUR (bir yargı çağrısında ayrışma en karar-ilişkili çıktıdır).

## Ne yapar
1. **Frame (decomposer, Opus)** — konuyu okur, ekseni seçer (temporal geçmiş-şimdi-gelecek / technical bileşenler / auto), 2-5 **örtüşmeyen (MECE)** dilim üretir; her dilime kapsam + kapsam-dışı + net sorular + derinlik (1x/2x) + stakes atar; kapsama-boşluklarını kendi raporlar.
2. **Evaluate (Opus, paralel)** — her dilim için `depth` kadar **bağımsız** Opus değerlendirici; yüksek-stakes/belirsiz dilimler 2x. Her değerlendirici yalnız kendi diliminin sorularını yanıtlar (kapsam-dışına çıkmaz).
3. **Reconcile** — 2x dilimlerde iki Opus'un ayrıştığı yerleri deterministik yakalar. **Ayrışma = sinyal**, ortalanmaz; iki görüş de taşınır. İki bağımsız Opus hemfikirse bu **güçlü güven sinyalidir**.
4. **Synthesize (Opus)** — tüm dilim yargılarını + ayrışmaları tek bir **karar artefaktına** birleştirir (zayıf-halka mantığı, ortalama değil) — dilim-bazlı rollup + genel öneri (go / koşullu-go / no-go / eksik-bilgi).

## Nasıl çalıştırılır
Bu skill **Workflow** aracını `supervisor-review` workflow'uyla çağırır. Konuyu `args` ile geç — serbest metin ya da yol/PR (karar/plan/tasarım/doküman/kod-alanı).
Opsiyonel — `args.axis` (`temporal` / `technical` / `auto`, vars. auto), `args.depth` (`all1x` / `all2x`, vars. decomposer-kararı), `args.maxSlices`.
Konu belirsizse çalıştırmadan önce kullanıcıya **SOR** (neyi, hangi eksende) — uydurma.

## Kurulum gereği (canlı çalışması için)
Workflow ajanları `agents/*` prompt'larını **kayıttan** çözer → `agents/` ve `workflows/` repo'dan `~/.claude/agents/` ve `~/.claude/workflows/` altına kopyalanmış olmalı (bkz. README Kurulum). Aksi halde `agentType` çözülemez. (Devir'le aynı "repo = `~/.claude` aynası" ilkesi.)

## Sınırlar / felsefe (abartısız)
- **Advisory, gate değil** — çıktı incelenebilir bir karar artefaktı; otomatik commit/fix YOK, insan döngüde.
- **Eksen tek seçilir** — eksen karıştırmak örtüşme yaratır; decomposer tek eksen seçip gerekçesini yazar (2-D matris kapsam dışı, gelecek-iş).
- **2x = yedeklilik değil, ölçüm** — değer çıktıyı ikilemekte değil, ANLAŞMAZLIĞI ÖLÇMEKTE; hem hemfikirlik hem ayrışma bilgidir.
- **Maliyet** — çok-Opus, token-yoğun; 2x dilimleri ikiye katlar. Bütçeye göre dilim sayısı/derinlik ölçeklenir. Küçük/net konularda `/code-review` veya tek skill yeter — bu, yüksek-stakes, çok-yönlü kararlar içindir.
- Değerlendirme **uydurulmaz** — emin olunmayan dilim düşük-confidence/açık-soru olarak işaretlenir; bloke/incelenmemiş dilim genel kararı 'eksik-bilgi'ye çeker (sahte-temiz değil).
