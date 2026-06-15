# Diyagramlar + güncelleme disiplini

Diyagramlar **türetilmiş artefakt**tır; kaynak her zaman koddur (`skills/`, `hooks/`,
`settings.example.json`). Skill/hook değişince diyagram da güncellenmeli — yoksa doküman
yalan söyler. Bu dizin hem şemaları hem de o senkronu koruyan kuralı/araçları tutar.

## Şemalar

| Dosya | Ne gösterir | Kaynak (source of truth) |
|-------|-------------|--------------------------|
| [`devir-trigger-flow.svg`](devir-trigger-flow.svg) | Kullanıcı tetikleri (/devir · /devir-resume · /devir-land) vs L3 hook akışı (tek bakışta) | `skills/*/SKILL.md`, `hooks/devir-*.py`, `settings.example.json` |
| [`devir-trigger-flow.en.svg`](devir-trigger-flow.en.svg) | Yukarıdakinin **İngilizce aynası** (README.md'ye gömülü); kanonik kaynak Türkçe SVG'dir | `devir-trigger-flow.svg` (1:1 çeviri) |
| `../workflow.md` (Mermaid ×3) | Mimari · tam lifecycle · güvenlik-ağı sequence | `skills/devir/*`, `skills/devir-resume/SKILL.md`, `skills/devir-land/SKILL.md`, `hooks/*` |

> `devir-trigger-flow.svg` **standalone**'dur (inline hex, her yerde render olur — GitHub/tarayıcı).
> İnline gösterilen renkli sürüm visualize-host CSS class'larına dayanır; bu dosya ona bağlı değildir.
>
> `devir-trigger-flow.en.svg`, Türkçe SVG'nin **birebir İngilizce aynasıdır** (README.md'ye gömülü).
> Türkçe SVG yapısal değişirse (kutu/akış/etiket), `.en.svg` de elle senkronlanmalı — kanonik kaynak Türkçe SVG.

## Kural — skill/hook değişince

1. **Sabit/eşik** değiştiyse (ör. `THRESHOLD`, `INJECT_CAP`, pencere boyutları): `workflow.md §8`
   tablosunu güncelle. Sonra `tools/check_doc_sync.py`'yi koş — drift'i o yakalar.
2. **Hook event wiring** değiştiyse (`settings.example.json`): `workflow.md` tetik tablolarını
   (A/B) ve gerekiyorsa `devir-trigger-flow.svg`'deki kutuları güncelle.
3. **Yapısal** değişiklik (yeni faz, yeni hook, akış değişimi): hem Mermaid bloklarını hem
   `devir-trigger-flow.svg`'yi **elle** güncelle (yapısal drift otomatik yakalanamaz).
4. PR/commit'ten önce: `python3 tools/check_doc_sync.py` yeşil olmalı.

## Otomatik kontrol

[`tools/check_doc_sync.py`](../../tools/check_doc_sync.py) — vendored hook'lardaki sayısal
sabitleri ve `settings.example.json`'daki hook event'lerini çıkarır, `workflow.md`'de geçtiklerini
doğrular. Drift varsa exit 1 + rapor. (Sabit/wiring drift'ini yakalar; **yapısal** diyagram
doğruluğu hâlâ insan gözü ister — §3.)

```bash
python3 tools/check_doc_sync.py
```

> İsteğe bağlı: bu komut bir `PreToolUse`/CI adımına bağlanarak gate'e çevrilebilir; şu an
> advisory (devir'in kendi advisory-vs-gate felsefesiyle tutarlı).
