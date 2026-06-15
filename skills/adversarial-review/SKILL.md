---
name: adversarial-review
description: Değişen kodu çok-eksenli (correctness + security + reuse) ADVERSARIAL incele — bulucular bulur, bağımsız Opus şüpheciler her bulguyu ÇÜRÜTMEYE çalışır, çoğunluk çürütemezse bulgu ayakta kalır (sahte-pozitif öldürme), yeni bulgu bitene kadar loop-until-dry. Ağır iş workflows/adversarial-review.js'de (model-per-role, agents/* özel prompt'ları). Kullanıcı "adversarial review", "şu diff'i derinlemesine incele", "bulguları doğrulat", "review et ve çürüt" derse. Mimari — ../../docs/architecture.md.
disable-model-invocation: true
allowed-tools: Bash(git:*), Read, Grep
---

# /adversarial-review — bul → çürüt → doğrulananı raporla

`/code-review`'in yapısal-titizlik tümleyeni: tek bir reviewer yerine **çok-eksenli bulucu + adversarial doğrulama**.
İnce giriş budur; orkestrasyon `workflows/adversarial-review.js`'de (deterministik fan-out).

## Ne yapar
1. **Scope** — değişen dosyalar + satır-referanslı diff digest (bir ajan).
2. **Find (Sonnet ×3 eksen)** — `agents/reviewer-correctness`, `reviewer-security`, `reviewer-reuse` paralel bulur.
3. **Verify (Opus ×N)** — her **taze** bulgu için bağımsız `agents/skeptic-verifier` şüpheciler onu **çürütmeye** çalışır; **çoğunluk çürütemezse** bulgu kalır (belirsizlik = refuted → sahte-pozitif düşer).
4. **Loop-until-dry** — yeni bulgu üretmeyen ardışık 2 tur olana dek (≤4 tur) tekrarla; sonra Opus sentez raporu.

## Nasıl çalıştırılır
Bu skill **Workflow** aracını `adversarial-review` workflow'uyla çağırır. Hedefi `args` ile geç:
- Varsayılan (arg yok): **mevcut branch'in main'e göre diff'i** (`git diff main...HEAD`).
- Özel: bir PR numarası, dosya kümesi veya `git diff <ref>` ifadesi (ör. `args: "HEAD~3...HEAD"`).

Çalıştırmadan önce kapsamı netleştir: hedef belirsizse kullanıcıya **SOR** (hangi branch/PR/diff), uydurma.

## Kurulum gereği (canlı çalışması için)
Workflow ajanları `agents/*` prompt'larını **kayıttan** çözer → `agents/` ve `workflows/` repo'dan
`~/.claude/agents/` ve `~/.claude/workflows/` altına kopyalanmış olmalı (bkz. README Kurulum). Aksi halde
`agentType` çözülemez. (Devir'le aynı "repo = `~/.claude` aynası" ilkesi.)

## Sınırlar / felsefe (abartısız)
- **Advisory, gate değil** — devir'in çizgisiyle tutarlı. Bulgular **öneri**dir; uygulamak/atlamak kullanıcının.
- **İnsan döngüde:** rapor incelenebilir bir artefakt; otomatik commit/fix YOK (isteyen `/code-review --fix` kullanır).
- **Maliyet:** çok-ajanlı + Opus doğrulama token-yoğundur; küçük diff'lerde `/code-review` yeterli olabilir. Bu skill **derin/kritik** inceleme içindir.
- Bulgu **uydurulmaz**: bulucu tekrar-senaryosu kuramazsa, şüpheci çürütürse → düşer.
