# Mimari — claude-harness

> Bu repo bir **kişisel orchestration harness**'ın yayımlanmış aynasıdır: Claude Code'un üstüne kurulu,
> elle tasarlanmış skill + agent + workflow + hook katmanları. Source of truth = `~/.claude/`; repo snapshot.
> Bu doc tek resmi tutar; alt-sistemlerin *neden*'i kendi doc'larında (devir → [`workflow.md`](workflow.md) +
> [`../skills/devir/DESIGN.md`](../skills/devir/DESIGN.md)).

## Neden "harness"

Tek bir güçlü komut (ör. Fable/Opus) kompleks işi uçtan uca bitirebilir. Ama iki şey elle kurulmuş yapı ister:
**(1) süreklilik** — bir session context sınırına çarpınca state'i kaybetmemek; **(2) titizlik** — bir değişikliği
tek bakışla değil, çok-eksenli + adversarial doğrulamayla incelemek. `claude-harness` bu ikisini iki alt-sistem olarak
modelliyor: **devir** (süreklilik) ve **adversarial-review** (titizlik). İkisi de aynı dört katmanı paylaşır.

## Dört katman

| Katman | Dizin | Ne | Kim çalıştırır |
|---|---|---|---|
| **Skills** | `skills/*/SKILL.md` | İnce **tetik** + ince mantık; `disable-model-invocation: true` (yalnız kullanıcı) | Kullanıcı (`/devir`, `/devir-resume`, `/devir-land`, `/devir-archive`, `/adversarial-review`) |
| **Agents** | `agents/*.md` | Subagent **özel prompt'ları** (frontmatter `name`/`model`/`tools`) — rol-başına model | Workflow ya da `Task`/`agentType` |
| **Workflows** | `workflows/*.js` | **Deterministik orchestration** (fan-out/loop/conditional) — ağır iş burada | `Workflow` aracı (skill'den) |
| **Hooks** | `hooks/devir-*.py` | **Advisory güvenlik ağı** (L3) — model işbirliği gerekmeden mekanik | Claude Code event'leri (`settings.json`) |
| *(araçlar)* | `tools/` | Drift guard (`check_doc_sync.py`), ileride sync/eval | Manuel / CI |

**İlke — ince skill, ağır workflow.** Skill sadece tetikler ve kapsamı netleştirir; çok-ajanlı mantık `workflows/`'a iner.
Bu, mantığı deterministik ve test edilebilir tutar (model-güdümlü değil, kod-güdümlü kontrol akışı).

**İlke — model-per-role.** Ucuz/paralel iş (bulucular, mekanik scope) Sonnet; pahalı/yargısal iş (adversarial şüpheci,
sentez) Opus. Atama agent dosyalarının `model:` frontmatter'ındadır → workflow rolü seçer, modeli agent taşır.

**İlke — repo = `~/.claude` aynası.** Skill'ler/hook'lar/agent'lar/workflow'lar canlı kurulumda yaşar; repo onların
yayımlanmış snapshot'ı. Bu yüzden kurulum düz kopyadır ve `check_doc_sync.py` kod↔doc drift'ini advisory yakalar.

## Alt-sistem 1 — devir (süreklilik)

Context ~300k degradation bölgesine girmeden state'i kalıcı katmanlara flush et → temiz session'da güvenli devam.
Üç persistence katmanı (L1 global memory · L2 lokal not · L3 hook ağı) + üç skill:

- `/devir` — yarım iş ~260k'ya çarpınca: state'i yakala → L1+L2 yaz → handoff → opt-in commit.
- `/devir-resume` — fresh session'da: not seç → staleness (git-drift) → onay → devam (**handon**).
- `/devir-land` — biten kapalı dilimi aynı session'da indir (DONE GATE → cerrahi pathspec → rebase-before-push).
- `/devir-archive` — harcanmış/bayat notları `archive/`'e MANUEL + non-destructive (`mv`, asla `rm`) taşı; SessionStart "🗄️ arşiv adayı" banner'ının karşılığı.

Detay + diyagramlar: [`workflow.md`](workflow.md). Tasarım gerekçeleri: [`../skills/devir/DESIGN.md`](../skills/devir/DESIGN.md).

## Alt-sistem 2 — adversarial-review (titizlik)

`/code-review`'in **yapısal-titizlik** tümleyeni: tek reviewer yerine çok-eksenli bulucu + adversarial doğrulama.

```
Scope (1 ajan: değişen dosyalar + diff digest)
  └─► Find  (Sonnet ×3: correctness · security · reuse)        ┐
        └─► dedup (görülenlere karşı)                          │ loop-until-dry
              └─► Verify (Opus ×N şüpheci/bulgu → ÇÜRÜT)       │ (≤4 tur, 2 kuru tur → dur)
                    └─► çoğunluk çürütemezse → ayakta kalır    ┘
  └─► Synthesize (Opus: doğrulanan bulgulardan rapor)
```

- **Bulucular** (`agents/reviewer-correctness|security|reuse`, Sonnet): her biri kendi ekseninde, **önce-oku-sonra-iddia-et** disipliniyle, tekrar-senaryosu kurulabilen bulgular üretir.
- **Şüpheci** (`agents/skeptic-verifier`, Opus): tek bulguyu **çürütmeye** çalışır; belirsizlik = refuted → sahte-pozitif ölür.
- **Çoğunluk oyu + loop-until-dry:** bir bulgu, şüphecilerin çoğunluğu onu çürütemezse kalır; yeni bulgu üretmeyen ardışık 2 tur olana dek aranır (uzun-kuyruk bug'ları için).
- Orkestrasyon: [`../workflows/adversarial-review.js`](../workflows/adversarial-review.js). Tetik: [`../skills/adversarial-review/SKILL.md`](../skills/adversarial-review/SKILL.md).

**Advisory, gate değil.** Devir'le aynı felsefe: bulgular öneridir, insan döngüde; otomatik commit/fix yok.

## Drift disiplini

`tools/check_doc_sync.py` (advisory): hook sabitleri, hook-wiring, **skill adları** (workflow.md/architecture.md'de belgeli mi),
ve **agent-wiring** (`workflows/*.js`'in andığı her `agentType` için `agents/<ad>.md` var mı) drift'ini yakalar.
Yapısal diyagram doğruluğu insan işidir (bkz. [`diagrams/README.md`](diagrams/README.md)).
