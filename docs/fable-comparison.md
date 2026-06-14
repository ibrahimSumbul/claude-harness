# Orchestration Yaklaşımımız vs Anthropic Fable — Kanıta Dayalı Karşılaştırma

> Bu doküman bilinçli olarak **kanıta dayalı hipotez** tonunda yazıldı: doğrulanmış olan
> kaynakla işaretlenir, çıkarım "çıkarım" diye, bilinmeyen "bilinmeyen" diye etiketlenir.
> Amaç abartmak değil, **savunulabilir** bir resim çizmek.

---

## 0. Önce dürüst başlık (BLUF)

Başlangıç hipotezi şuydu: *"Fable aslında bağımsız bir model değil; skill-set'leri ve
workflow'ları yöneten bir Opus agent'ıdır; diff review'u 3x yapar."*

**Bu hipotez kamuya açık kanıtla DESTEKLENMİYOR ve birincil kaynaklarla çelişiyor** — kanıt-yokluğu
+ Fable/Mythos *aynı-weights* gerçeği temelinde **güçlü çıkarım**; doğrudan mimari ifşa değil
(bkz. kapanış kaydı). Kolayca yanlışlanabilir bir iddianın üzerine portföy kurmak
("Fable = sadece Opus + skill") *abartma* olurdu ve ilk teknik soruda çökerdi. Onun yerine
**daha güçlü ve doğru bir tez** var:

> Senin elle kurduğun orchestration pattern'i (akıllı bir koordinatör + rol-ayrışmış daha ucuz
> worker'lar + adversarial doğrulama) **gerçek, değerli ve sektörün Fable ile *kurduğu*
> pattern'in ta kendisi.** Fable'ın *içinde* değil — Fable'ın *üstünde*.

Ve asıl staff-level nokta karşılaştırmanın kendisi değil, **mühendislik yargısı**: monolitik model
güçlü default'tur; elle orchestration yalnızca yüksek-bahisli, ayrıştırılabilir, doğrulanabilir
işte — ve bir eval lift'in çarpanı (3-15× token) geçtiğini kanıtladığında — yapılan bir yatırımdır.
Fable bu yargının fonu, başlığı değil. Aşağısı hepsini kaynaklarıyla gösterir.

---

## 1. Fable gerçekte ne? (kanıt)

| İddia | Verdict | Kaynak |
|-------|---------|--------|
| Fable 5 kamuya **bağımsız frontier model** olarak sunuluyor (wrapper/agent değil) | **Desteklenir** | [A1][A2][A3] |
| `claude-fable-5`; 1M context; ≤128k output; $10/$50 per M; 2026-06-09 | **Desteklenir** | [A2] |
| Fable 5 ve Mythos 5 **aynı weights**; Mythos = classifier'ları kaldırılmış hali | **Desteklenir** | [A2][S2] |
| Opus 4.8 yalnızca **refusal-fallback** olarak devrede (cyber/bio/chem/distillation/frontier-dev flag'lenirse) | **Desteklenir** | [A1][A2][N1] |
| Fallback classifier reddiyle tetiklenir (`stop_reason: "refusal"`), `fallbacks` param / middleware / manuel retry ile yürür | **Desteklenir** | [A2] |
| Session'ların **%95+'ı hiç fallback gerektirmeden** Fable'ın kendi cevaplarıyla çalışıyor; Opus yalnız flag'lenen küçük dilimde | **Desteklenir** | [A3][N1] |
| "Kendi işini doğrular / kontrol eder" = **model-içi** davranış, harici review wrapper değil | **Çıkarım** [A1][A3] |
| Fable bir "Opus + skill/workflow orchestration katmanı" **değildir** | **Çıkarım (güçlü)** — aynı-weights + tek-model çerçevesinden çıkar [A2][S2] |
| Fable "3x diff review" / sabit N-pass yapar | **KANIT YOK** — docs, product/news, day-one reporting ve sistem-kartı analizlerinde hiç geçmiyor |
| Fable içeride Opus üzerinde skill/workflow orchestrate eder (orijinal hipotez) | **KANIT YOK / ÇELİŞİLİYOR** |
| Fable'ın gerçek training recipe / düşük-seviye mimarisi | **BİLİNMİYOR** — açıklanmamış [S1][S2][S3] |

**En kritik anti-hipotez gerçeği:** Fable ve Mythos *aynı weights*'i paylaşıyor (Mythos =
classifier'ları kaldırılmış Fable). Tek fark bir güvenlik/classifier katmanı; Opus yalnızca
*reddedilen* istekte erişilebilir. Bu, "tek eğitilmiş model + classifier katmanı" resmini
neredeyse kesinleştirir ve "orchestration stack'i" okumasını dışlar.

---

## 2. "Orchestration" kelimesi — ama ters yönde

Fable etrafında "orchestration" dili **var**, ancak hipotezin tersi yönde: üçüncü-parti
rehberler *Fable'ı orchestrator olarak* tarif ediyor — akıllı "beyin" en üstte, ucuz
sub-agent'ları (sonnet/haiku) yöneten. Yani **Fable, Opus'un üstünde oturur, altında değil**
([B1][B2]). Kullanıcının muhtemelen karşılaştığı şey bu topluluk pattern'i; yönü ters okunmuş.

Bu bizim için iyi haber: **bizim devir + multi-pass review tasarımımız tam da bu "akıllı
koordinatör + ucuz worker" pattern'inin elle kurulmuş bir örneği.** Fark, Fable kullanıcısının
bunu hazır bir frontier model üstüne kurması; bizim ise harness + hook + skill katmanında
*kendimiz* kurmamız.

---

## 3. İki paradigma (asıl savunulabilir karşılaştırma)

Doğru kıyas "Fable 3x yapar, biz 1x+..." değil — çünkü Fable'ın 3x'i belgelenmemiş. Doğru
kıyas **paradigma** düzeyinde:

**(A) Monolitik model + iç akıl yürütme.** Tek model instance, görevi uçtan uca yapar; uzun
internal chain-of-thought üretir, alternatifleri dener, commit'ten önce kendini eleştirir.
Test-time compute *tek* autoregressive akışın içinde harcanır. Fable'ın "en yüksek effort'ta
kendi işini gözden geçirir ve doğrular" davranışı buraya düşer — self-review *aynı context'te*
taslağı yeniden okumaktır, yapısal olarak bağımsız bir kontrol değil. Hata *korelasyonlu*
(erken yanlış varsayım tüm zinciri zehirler).

**(B) Elle kurulmuş agentic orchestration.** Harici bir kontrol katmanı (senin kodun, modelin
değil) görevi parçalar, modeli farklı rollerle farklı prompt'larla *birden çok kez* çağırır,
sonra birleştirir. Örnek: *1 Opus reviewer + 2 Sonnet pass + adversarial verify + majority
vote.* Klasik orchestrator-worker topolojisi: her pass kendi *taze context*'inde koşar (hata
*decorrelated*), sonra deterministik bir aggregation (vote/merge) nihai çıktıyı üretir.
"Zeka"nın bir kısmı modelde, bir kısmı **incelenebilir/düzenlenebilir** orchestration kodunda.

Yapısal fark: (A)'da akıl yürütme *bağlı ve paylaşımlı* (tek context, korelasyonlu hata);
(B)'de *ayrışmış ve izole* (bağımsız context, kısmen decorrelated hata + denetlenebilir kontrol).

### Neden "3x"? — self-consistency

Teorik temel **self-consistency** (Wang et al., 2022): stokastik decoding'le birden çok akıl
yürütme yolu örnekle, tek greedy decode yerine çoğunluğu al. Doğru cevaplar bağımsız
zincirlerde pekişir, hatalar dağılır (GSM8K'da +%17.9). **N=3 neden:** N=1 varyans sinyali
vermez; **N=3, tek aykırıyı 2-of-3 çoğunlukla ezebilen en ucuz tek sayıdır** (tek sayı →
beraberlik yok); 3→11 az fayda, lineer maliyet. **Uyarı:** self-consistency *kontrol edilebilir,
ayrık* bir cevap varsayar. Kod/prose gibi açık-uçlu çıktıda token-bazlı oylama işlemez →
bir *aggregator* (yargıç) gerekir — bizim *hedeflediğimiz* akışta **Opus reviewer'ın iki Sonnet
pass'ini adjudike etmesi** ("universal self-consistency"). Yani Opus+2×Sonnet ≈ *daha güçlü
aggregator'lı self-consistency*: ucuz çeşitli örnekler + pahalı bir hakem. (Bu **hedeflenen**
orchestration; henüz eval'le doğrulanmadı — bkz. §5.)

### Trade-off'lar

| Boyut | (A) Monolitik | (B) Orchestration (Opus + 2×Sonnet + vote) |
|-------|---------------|--------------------------------------------|
| **Latency** | Düşük; tek tur | Yüksek (paralel değilse). Fan-out eşzamanlı koşabilir; verify/vote serial kuyruk. |
| **Token/$ ** | 1× | Çarpımsal ~3-5×; production multi-agent ~**15×** token. Doğruluğun bir kısmını *satın alıyorsun*. |
| **Güvenilirlik** | Güçlü ama hata *korelasyonlu* | Decorrelated pass + adversarial verify → daha yüksek recall, daha az false-positive. Anthropic'in multi-agent'ı bir research eval'de tek-agent Opus'u ~%90 geçti. |
| **Determinizm** | temp 0'da daha deterministik | Çeşitlilik temp>0 ister; ama *aggregation* (eşik/merge) deterministik kod → karar mantığı tekrarlanabilir. |
| **Debuggability** | Zayıf (tek opak blob) | İyi: her pass + verify verdict + vote sayımı incelenebilir artefakt; tek rolü ayrı tune edersin. |
| **Mühendislik maliyeti** | ~Sıfır | Gerçek: orchestration kodu, rol-başına prompt, retry/timeout/partial-failure, eval harness. |

**İki senior uyarı (dürüstçe):**
1. **Oylama yalnızca pass'ler gerçekten bağımsızsa işe yarar.** Aynı model + aynı prompt +
   düşük temp → korelasyonlu hata → çoğunluk ortak yanlışı *onaylar*. Çeşitlilik (farklı model,
   rol prompt, sıcaklık) yük taşıyan varsayımdır, oylamanın kendisi değil.
2. **Orchestration bedava zeka değildir.** Güvenilirlik + gözlenebilirliği token, latency ve
   mühendislik karmaşıklığı ile *satın alır*. Dürüst çerçeve: **(A) güçlü default'tur; (B) ise
   yüksek-bahisli, ayrıştırılabilir, doğrulanabilir işlerde — ve ancak bir eval lift'in
   çarpanı geçtiğini kanıtlarsa — yaptığın bir güvenilirlik/denetlenebilirlik yatırımıdır.**

---

## 4. Bizim sistem bu haritada nerede? (kanıtla, düzeltmelerle)

Kendi kurulumumuzu olduğu gibi haritaladık. Önemli **doğruluk düzeltmeleri** dahil:

- **"3x diff review"e en yakın şey `simplify`.** `simplify` review'u birden çok kalite boyutunda
  (reuse / simplification / efficiency / altitude) yapıp düzeltir; gözlemlediğimiz davranış Task
  tool ile paralel bir 3-agent fan-out (fan-out binary'de doğrulandı). ⚠ İki kayıt: (a) tam
  topoloji/agent sayısı ve "bug avlamaz, onun için /code-review" ifadesi *çalışan harness
  açıklamasından* — belgelenmiş bir garanti değil; (b) bu fan-out **kalite odaklı**, correctness-bug
  avı değil.
- **"diff review 1x" = tek-pass reviewer'lar:** `engineering:code-review` (single-pass,
  security/perf/correctness/maintainability), built-in `review` (PR), ve `code-review`'un
  low/medium effort'u ("daha az, yüksek-güvenli bulgu").
- **"Case-specific subagent" = iki gerçek mekanizma:** `security-review` allowed-tools'unda
  `Task` taşır → odaklı güvenlik subagent'ı açabilir; `verify` ise *yüzeye-özgü* (CLI/server/
  GUI/library/agent/CI) davranış-agent'ı, repo'nun `verifier-*` skill'ini çağırır.
- **⚠ "Opus 1x, Sonnet 2x" model ataması hiçbir skill'de tanımlı DEĞİL.** `simplify`'ın
  3'lü fan-out'u model **belirtmez**; tüm review skill'leri model-agnostik. Yani Opus/Sonnet
  rol-başına atama **senin kendi orchestration katmanın** — skill'in özelliği değil. (Bu, doğru
  ve dürüst bir kabul: kıymetli olan kısım *senin* kararın.)
- **"ultra / cloud fleet" ayrı bir kademe:** kurulu binary 2.1.132'de *doğrulanmış* olan
  `ultrareview`'dır ("multi-agent review fleet ile bug bulur ve doğrular", `claude --remote`
  gerekli, USD maliyet tahminli). Daha yeni harness'ın tarif ettiği `code-review --ultra`
  ("bulutta derin multi-agent review") aynı soyun devamı görünüyor ama davranışı *açıklamadan*
  okundu, on-disk doğrulanmadı. Asıl mimari fark *off-box (cloud)* koşması — ham "1x vs 3x"
  sayısından daha önemli.

**Sonuç:** yerel skill yüzeyi şunu sunuyor — (1) yalın tek-pass review, (2) gerçek 3-paralel
*kalite* fan-out (`simplify`), (3) case-specific specialist agent'lar (`security-review`+Task,
`verify`), (4) cloud multi-agent fleet (`ultrareview`). **Opus-1x/Sonnet-2x split'i senin
sağladığın orchestration'dır; skill'ler model-agnostiktir.** Bu, paradigma (B)'nin somut,
elle-kurulmuş bir örneğidir — üstüne bir de devir ile *süreklilik/state* boyutunu ekliyor.

---

## 5. Reflektif: gerçekten "senior AI engineer işi" mi?

Dürüst değerlendirme — abartısız, savunmasız.

**Gerçekten senior olan kısımlar (savunabiliriz):**
- **Context engineering / reliability infra:** devir, "long-context degradation"ı bir
  *operasyonel risk* olarak modelleyip üç-katmanlı, fail-safe bir kurtarma ağı kuruyor.
  Bu, prompt yazmaktan farklı bir disiplin — sistem mühendisliği.
- **Doğru failure-mode refleksleri:** her hook'un exit-0 garantisi (compaction'ı asla kırma),
  `flock`+atomik+idempotent index (paralel-session race), cap-öncesi redaction (sınır-aşan
  secret sızıntısı), fence-aware extraction (gerçek bir prod bug yakalandı), staleness
  ref-guard (`2>/dev/null` ile FRESH sanma tuzağına düşmeme). Bunlar deneyimli birinin
  düşündüğü kenar durumlar.
- **Advisory-vs-gate ayrımı + platform limitinin bilinçli kabulü** (Anthropic #43733'e atıf):
  "zorlayamıyorum, o yüzden deterministik ağı ayrı tutuyorum" — olgun bir tasarım kararı.
- **Adversarial doğrulama refleksi:** bu karşılaştırmanın kendisi bir generate→verify
  workflow'uyla üretildi; Fable iddiaları kanıta göre süzüldü. Süreç, paradigma (B)'yi
  *uyguluyor*.
- **Kanıta dayalı düşünme:** §0'da kendi başlangıç hipotezi kanıt karşısında terk edilip
  yerine kaynaklı bir tez konuldu (savunmacı değil, yargıyı okuyucuya bırakan bir hamle).

**Table-stakes / abartmamamız gerekenler:**
- `simplify`'ın 3x'i ve `ultrareview` Anthropic'in **hazır** verdiği şeyler; bizim katkımız
  onları *orkestre etmek* (model-per-role, devir ile birleştirme), icat etmek değil.
- Tek-makine, tek-kullanıcı kurulum; dağıtık/çok-kullanıcılı production sertliği henüz yok.

**Eksik / dürüstçe söylenmesi gerekenler:**
- **Eval yok.** Paradigma (B)'nin altın kuralı: "lift'in çarpanı geçtiğini bir eval kanıtlamalı."
  Bizim multi-pass review'un tek-pass'e karşı ölçülmüş bir kazanımı henüz yok — bu, bir sonraki
  somut senior adımı.
- **Pass bağımsızlığı kanıtlanmadı.** Opus+2×Sonnet'in oyları gerçekten decorrelated mı, yoksa
  ortak prompt/bias mı paylaşıyor — ölçülmedi.
- **Kendi maliyet/latency profilimiz ölçülmedi.** §3'teki 3-15× token ve serial verify kuyruğu
  *bizim* kurulumumuz için de geçerli; lift'i bu çarpana karşı tartmadık (paradigma B'nin kendi
  koyduğu bar).

**Net:** Yukarıdaki reliability detayları (exit-0 garantileri, flock idempotent index, cap-öncesi
redaction, fence-bug yakalama, staleness ref-guard) ve eksiklerin (eval-yok, ölçülmemiş maliyet)
açıkça işaretlenmesi kıdemli pratiklerle tutarlı — seniority'yi doküman *iddia etmez*, bu
artefaktlar gösterir. "Fable'ı çözdük / Fable bizim yaptığımız şey" çerçevesi ise yanlış olurdu.
Savunulabilir çerçeve: **"Frontier model üreticilerinin kullanıcılara önerdiği orchestration
pattern'ini, harness/hook/skill katmanında elle, fail-safe ve süreklilik-bilinçli biçimde kurduk;
bir sonraki adım onu eval ile kanıtlamak."**

---

## Kaynaklar

**Resmî / birincil**
- [A1] Claude Fable ürün sayfası — https://www.anthropic.com/claude/fable
- [A2] API docs, "Introducing Claude Fable 5 and Claude Mythos 5" — https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5
- [A3] Anthropic news, "Claude Fable 5 and Claude Mythos 5" — https://www.anthropic.com/news/claude-fable-5-mythos-5

**Haber / raporlama**
- [N1] TechCrunch — https://techcrunch.com/2026/06/09/anthropic-released-claude-fable-5-its-most-powerful-model-publicly-days-after-warning-ai-is-getting-too-dangerous/

**Sistem-kartı / analiz**
- [S1] Simon Willison, "If Claude Fable stops helping you, you'll never know" — https://simonwillison.net/2026/Jun/10/if-claude-fable-stops-helping-you/
- [S2] Zvi Mowshowitz, "Claude Fable 5 and Mythos 5: The System Card" — https://thezvi.substack.com/p/claude-fable-5-and-mythos-5-the-system
- [S3] Nathan Lambert (Interconnects) — https://www.interconnects.ai/p/claude-fable-5-and-new-ai-safety

**"Fable-as-orchestrator" topluluk pattern'i (mimari iddia DEĞİL, terminoloji bağlamı)**
- [B1] Developers Digest, "The Fable 5 Orchestrator Playbook" — https://www.developersdigest.tech/blog/fable-5-orchestrator-model-playbook
- [B2] Cloudzy, "Fable 5 in Claude Code: What Actually Changed" — https://cloudzy.com/blog/fable-5-in-claude-code-what-changed/

**Paradigma / self-consistency**
- Wang et al., 2022 — Self-Consistency Improves Chain-of-Thought Reasoning — https://arxiv.org/abs/2203.11171
- Universal Self-Consistency (2023) — https://arxiv.org/pdf/2311.17311
- How Anthropic built a multi-agent research system (orchestrator-worker, ~%90 lift, ~15× token) — https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent

---

> **Dürüstlük kaydı:** Fable detaylarının bir kısmı WebFetch özetleyicisinden geldi. Yük taşıyan
> gerçekler (tek model, Fable/Mythos aynı weights, Opus-yalnız-refusal'da, ~%95 session) birden
> çok bağımsız kaynakta doğrulandı. Fable'ın *iç mimarisi* "tek model + classifier + Opus
> refusal-fallback"ın ötesinde açıklanmamıştır — bu yüzden ne "Fable = sadece Opus+skill+3x"
> ne de "Fable kesinlikle sıfırdan pretrain" iddiası kanıtlanabilir; anti-hipotez sonucu
> *kanıt-yokluğu + aynı-weights gerçeği* temelinde **güçlü** ama doğrudan mimari ifşa değildir.
