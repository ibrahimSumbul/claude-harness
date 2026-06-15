---
name: devir
description: Session devir-teslim / context flush — context ~260k'ya ulaşınca MANUEL çalıştır. Canlı git/branch/worktree state'ini komutla yakala, in-flight + denenen/başarısız + kararları yaz, L1 memory (birincil) + L2 lokal unique-ID not (.claude/docs/devir-notes/, varsayılan lokal — commit opt-in) üret, MEMORY.md'yi flock-helper ile çakışmasız güncelle, non-destructive stale-fix yap, verbatim handoff bloğu + opt-in commit kapanışı → fresh session'a geç. Mimari/karar gerekçeleri: DESIGN.md.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh:*), Bash(pnpm:*), Bash(openssl:*), Bash(python3:*), Bash(date:*), Read, Edit, Write, Grep
---

# /devir — Session Devir-Teslim (Context Flush) · v2

Context ~260k'ya ulaşınca **MANUEL** çalıştır. State'i kalıcı katmana yüksek-fidelity yaz → **fresh session** aç → ~300k degradation bölgesine girmeden kalite koru.
**Mimari, lifecycle, conflict, benchmark gerekçeleri → [`DESIGN.md`](DESIGN.md).** Bu dosya operasyonel adımlar.

**Üç katman (sen = L1+L2 yazarı):** L1 global memory (birincil) · L2 lokal unique-ID not (varsayılan lokal; **opt-in commit** ile durable/cross-machine) · L3 hook ağı (advisory nudge + mekanik draft + restore).

## İlkeler (önce oku)
- **Minimal & mekanik ol** — degraded context'tesin. Canonical doc'ları YENİDEN OKUMA. Faz 1 komut çıktıları + context'te olana dayan.
- **Mekanik kaynaktan üret, recall'dan DEĞİL.** "Ne yapıldı" = `git log main..HEAD`; "yarım kalan" = `git status` + test çıktısı. Emin değilsen **"(belirsiz)"** yaz, UYDURMA.
- **Non-destructive:** stale-fix + append. Merge/delete/retire YOK → adayları `⚠ Reconcile`'a, riskli kısmı fresh session'da `/consolidate-memory`.
- **MEMORY.md'yi ELLE EDİT ETME** — paralel-session race var; `devir_memory.py` helper ile yaz (Faz 3).

## Faz 0 — Hazırlık (ID + önceki notlar)
- Repo + branch + ID üret:
  - `git rev-parse --show-toplevel` (repo değilse → not L2 atlanır, sadece L1 memory + handoff bloğu)
  - `git branch --show-current` → branch; slug = küçük harf, `[^a-z0-9._-]`→`-`
  - ID: `<YYYY-MM-DD>-<branch-slug>-<rand6>`, rand6 = `openssl rand -hex 3`
- Notlar dizini: `<repo>/.claude/docs/devir-notes/` (yoksa oluştur). Arşiv: `.../archive/` (taranmaz).
- Önceki açık notları tara (`status: open|draft`, archive hariç). Bu branch/worktree için açık not varsa → handoff'ta belirt; eski `draft`'lar yeni `open`'la **superseded** olacak.

## Faz 1 — Canlı state (komut çıktısı, paraphrase DEĞİL)
- Worktree: `git rev-parse --show-toplevel` · Branch: `git branch --show-current`
- Working tree: `git status --short` · Son commitler: `git --no-pager log --oneline -5`
- Bu branch'in işi: `git --no-pager log --oneline main..HEAD 2>/dev/null | head -20` (main yoksa "(bilinmiyor)")
- Açık PR: `gh pr list --state open 2>/dev/null | grep . || echo "yok/bilinmiyor"` (gh unauth ise merge state UYDURMA)
- Kod değiştiyse: `pnpm test:run` + `pnpm exec tsc --noEmit` → çıktıyı **verbatim** al.

## Faz 2 — In-flight yakalama (mekanik)
- Bu session ne yapıldı (1-3 cümle, `main..HEAD` + status'tan) · alınan kararlar.
- **Nerede kalındı + sıradaki TAM adım** ← en kritik.
- **✗ Denenen/başarısız yollar (ZORUNLU):** kronolojik, her biri **sonuç + tam hata** ile. Fresh session aynı çıkmaza girmesin. (Yoksa açıkça "yok".) *Alanın en pahalı-yeniden-keşfedilen içeriği — atlamak devrin amacını bozar.*
- **Kararlar (ZORUNLU): seçilen VE reddedilen** (reddedilenin sebebiyle).
- Yarım dosya/test (Faz 1 `git status` + test çıktısından — tahmin değil).

## Faz 3 — L1 Memory (BİRİNCİL)
Auto-memory bölümü (system prompt) format/dizini tanımlar — ona uy.
1. **`session-state-<branch-slug>.md`** güncelle (branch-keyed → paralel branch'ler çakışmaz). MUTLAKA: **worktree path + branch + uncommitted(yes/no) + sıradaki tam adım + test/TSC durumu + son not id**. Mutlak tarih.
2. **Durable** karar/feedback/preference → yeni topic dosyası.
3. **Stale-fix (NON-destructive):** yanlış fact'i düzelt, göreli→mutlak tarih. Merge/delete YOK → `⚠ Reconcile`'a.
4. **MEMORY.md index — ELLE DEĞİL, flock-helper ile** (idempotent, çakışmasız):
   ```bash
   python3 ~/.claude/hooks/devir_memory.py upsert \
     --file "<MEMORY.md mutlak yolu>" \
     --key "session-state-<branch-slug>.md" \
     --line "- [Session state: <branch>](session-state-<branch-slug>.md) — resume point"
   ```
   Index ≤200 satır tut (her session yüklenir). Retention'ı topic dosyalarında gevşet.

## Faz 4 — CLAUDE.md (ikincil — varsa, write protokolüne UY)
- SADECE düzenlenecek section'ları oku (§2 faz/branch/PR · §3 karar log başa max 10 · §4 facts · §8 versiyon). Tüm dosyayı/canonical'ları değil.
- Worktree'de uncommitted kalırsa fresh-from-main görmez → kritik state zaten Faz 3'te memory'de.

## Faz 5 — L2 not yaz (lokal; promotion gate)
`<repo>/.claude/docs/devir-notes/<id>.md` yaz — frontmatter + zorunlu bölümler:
```md
---
id: <id>
session_id: (varsa)
branch: <branch>
worktree: <path>
created: <YYYY-MM-DDTHH:MM:SS±TZ>
status: open
tokens: <~token>
covers_since: <commit SHA tercih et (önceki devir commit'i / git rev-parse HEAD); bilinmiyorsa "session start">
---
# DEVİR — <id>
## Hedef
## Yapılan (main..HEAD + status)
## ✗ Denenen / başarısız (sonuç + tam hata)
## Kararlar (seçilen / reddedilen)
## ▶ RESUME (literal — fresh session'a yapıştırılabilir)
​```bash
git -C "<worktree>" checkout <branch>
<test/build komutu — ör. pnpm verify>
# İlk aksiyon: <sıradaki tam adım>
​```
```
**PROMOTION GATE** (`status: open` yazmadan ÖNCE self-validate — hepsi ✓ değilse `draft` bırak, eksiği handoff'ta belirt):
`Hedef dolu · ▶ RESUME dolu (literal komut) · ✗ Denenen non-empty (veya açık "yok") · Kararlar non-empty · hiç [TODO] kalmadı`.
Aynı branch/worktree için eski `draft` notları varsa → `status: superseded` yap (silme).

## Faz 6 — Handoff bloğu (verbatim, ekrana)
`▶ RESUME` boş/muğlaksa bloğu VERME — Faz 1-2'ye dön (hollow handoff = kötü devir).
```
═══ DEVİR TAMAM — <YYYY-MM-DD> ═══
Not: .claude/docs/devir-notes/<id>.md  (status: open)
Worktree: <path>
Branch: <branch>  |  Uncommitted: <yes/no>  |  Açık PR: <# / yok / bilinmiyor>
Bu session: <1 cümle>
✗ Denenen: <kısa — yoksa "yok">
Güncellendi: memory session-state-<branch> + (CLAUDE.md §<...> varsa)
⚠ Reconcile: <deferred adaylar — yoksa "yok">
▶ RESUME: <sıradaki tam adım>
═══════════════════
```

## Faz 7 — L2 not kapanışı (VARSAYILAN: lokal — commit OPT-IN)
**Varsayılan: commit ETME.** L1 memory + L2 not zaten makine-local; tek-makine solo'da L1 sürekliliği taşır, L2 git'e girmeyi yalnız **cross-machine** veya **takım/paylaşım** gerçekten gerekiyorsa hak eder (DESIGN §2). Not dosyası lokal diskte kalır; `.claude/docs/devir-notes/` **global gitignore'da** → `git status`'u kirletmez, public repo'da iç-state sızdırmaz.
- **Varsayılan yol (commit YOK):** handoff bloğunda nota **lokal yol** olarak işaret et + "(lokal, commit edilmedi)" de. Bitti — Faz 8'e geç.
- **Opt-in commit (yalnız cross-machine/takım gerekiyorsa):** kullanıcı isterse VEYA gerçek cross-machine/paylaşım ihtiyacı varsa → **öner + onay al** (otomatik commit yok), sonra:
  1. **Branch güvenliği:** `main`/protected ise → doğrudan commit ETME, `chore/devir-<tarih>` branch öner.
  2. **Kapsam (feature kodundan AYRI):** `.claude/docs/devir-notes/<id>.md` + değişen `CLAUDE.md` §2/§3 (+ bu session güncellenen canonical doc parçaları). Yarım feature kodu → ayrı PR.
  3. **`git add -f <kapsam>`** — not dizini gitignore'da olduğundan `-f` ŞART (cerrahi pathspec; asla `-A`/`-u`) → `git commit -m "chore(docs): session devir [<YYYY-MM-DD> <konu>]"` — **AI co-author trailer YOK** (kullanıcı tercihi; repo konvansiyonu trailer istiyorsa ona uy).
  4. `git status --short` ile doc kirli kalmadığını doğrula. Push: kullanıcı isterse.
- **▶ RESUME**'a "doc commit" yazma — bir sonraki **iş/kod** adımını yaz (kapanış bu fazda biter).

## Faz 8 — NOT2U (kullanıcı kılavuzu, ekrana)
```md
## NOT2U — Yeni session adımları
1. Faz 7 varsayılan = not LOKAL (commit YOK) → normalde aksiyon gerekmez. Yalnız cross-machine/takım için commit ettiysen kapsamı (+push) kontrol et.
2. Yeni Claude Code session'ı aç.
3. İlk mesaj: `/devir-resume`  (veya sadece `resume`).
4. Agent nottan ne anladığını + staleness + planı verince onay cümlesiyle devam ettir.
```

---
**Güvenlik ağı (KURULU, advisory):** yakalayamazsan L3 devreye girer — `devir-autotrigger.py` (~260k nudge), `devir-precompact.py` (compaction öncesi mekanik `draft` not + redaction), `devir-sessionstart.py` (compact'te RESUME auto-inject + startup'ta durum banner). Sınır: PreCompact lossy/mekanik (model üretmez → "sıradaki adım"ı bilemez). Temiz devir için yine **manuel /devir** şart. Gerekçe: [`DESIGN.md`](DESIGN.md).
