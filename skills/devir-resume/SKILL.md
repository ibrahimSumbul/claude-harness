---
name: devir-resume
description: Fresh session'da devir notundan GÜVENLİ devam (handon). Açık not(ları) tara → staleness (git-drift) kontrolü → nottan ne anladığını özetle → birden fazla aday varsa hangisini SOR → onay alınca uygula. Non-destructive (consumed flip geri-dönülebilir, asla silmez). Kullanıcı "resume", "devir notundan başla", "hand on", "kaldığımız yerden devam" derse.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh:*), Read, Edit, Grep
---

# /devir-resume — Devir notundan güvenli devam (handon)

Yeni session'da, işe atlamadan ÖNCE: doğru notu seç, ne anladığını doğrula, **belirsizlikte SOR**, onay al. Mimari: [`../devir/DESIGN.md`](../devir/DESIGN.md).

## Faz 1 — Notları bul
- Dizin: `<ana-worktree>/.claude/docs/devir-notes/` — **paylaşılan + kalıcı** (`git rev-parse --git-common-dir` ebeveyni; linked worktree'de bile ana checkout). Yoksa → Faz 5 (fallback). Notlar worktree prune'unda **kaybolmaz**; tüm worktree'ler aynı dizini görür.
- `status: open|draft` notları tara (archive/ + consumed/superseded hariç). Frontmatter oku (`branch, worktree, created, id, covers_since`).
- **Filtre sırası (DESIGN §4b — paylaşılan dizin):** notlar tek dizinde toplandığı için worktree-yolu artık **zayıf** sinyal; birincil = branch.
  1. **branch-match (birincil):** `note.branch` == mevcut branch (`git branch --show-current`)? (paylaşılan dizinde en güvenilir eşleştirme.)
  2. eşleşme yoksa → aynı ana-repodaki tüm açık notlara genişle (cross-worktree/makine) + Faz 4'te SOR.
- **Precedence:** `open` > `draft`; aynı branch için `open` varsa `draft` superseded (gösterme/uyar). Daha yeni `created` öne.

## Faz 2 — Seçim
- **0 not:** Faz 5 (L1 memory + ask).
- **1 not:** Faz 3 ile devam.
- **≥2 not (filtre sonrası):** branch-match ile tiebreak; hâlâ ≥2 ise → **numaralı liste sun ve SOR** (sessizce SEÇME):
  ```
  Bu worktree için N açık devir notu var:
   [1] <branch>  (<id>, <created>)  ▶ <RESUME 1. satırı>
   [2] <branch>  (<id>, <created>)  ▶ <RESUME 1. satırı>
  Hangisinden devam edeyim? (numara)
  ```

## Faz 3 — Staleness (git-drift) kontrolü
Seçilen notu körü körüne güvenme. Drift'i hesapla:
- **`covers_since` geçerli bir commit ref mi?** `git rev-parse --verify -q "<covers_since>^{commit}"` (note-id / "session start" REF DEĞİL — 0 sanma).
  - Geçerli → `git --no-pager log --oneline "<covers_since>..HEAD" | wc -l` (not sonrası commit sayısı).
  - Değil → zaman-bazlı: `git --no-pager log --oneline --since="<note.created>" | wc -l`.
  - **`2>/dev/null` ile hatayı yutup 0 = FRESH SANMA** — komut başarısızsa "drift bilinmiyor" de.
- `git status --short` → kirli/değişen dosyalar · mevcut branch ≠ `note.branch`? (divergence)
- **Worktree-uyumu (kaynak-çoğaltma koruması):** "doğru yerde miyim?" sinyali **birincil = worktree-yolu** (uncommitted iş + repo aynası orada yaşar; branch İKİNCİL — not, `branch` ≠ o worktree'nin branch'i olacak şekilde ayrı çalışma-yeri/source-of-truth belirtebilir, bu meşru). `git rev-parse --show-toplevel` ↔ `note.worktree`:
  - **Eşit** → doğru yerdesin, sessiz geç (branch `note.branch`'ten farklıysa en fazla tek-satır not; redirect VERME).
  - **Farklı / `note.worktree` prune** → Faz 4'te NET redirect (uydurma; notun `worktree`/`branch` + belirtilmişse "source of truth"/çalışma-yerini yansıt): *"Bu iş `<note.worktree>` worktree'sinde devam etmeli; bu session farklı yerde (`<current>`). Kaynakları ÇOĞALTMA — ya oraya geç ya da oradaki repo aynası + global/source-of-truth kurulumu hedefle; bu worktree'ye yazma."* (prune ise: branch-match'e düş + source-of-truth'tan per-file re-sync öner.)
- Verdict (tek satır): **FRESH** (0 commit, doğru worktree) · **SLIGHTLY STALE** (1-2 commit) · **STALE** (≥3 / dünya kaymış / **drift bilinmiyor**) · **MISPLACED** (zaman olarak taze ama `toplevel ≠ note.worktree` — yukarıdaki redirect'i ver, "dünya kaymış" deme).
- STALE ise: "Not yazıldığından beri dünya kaymış (<özet>). Körü körüne devam yerine önce yeniden doğrulayalım mı?" → kullanıcıya bırak.

## Faz 4 — Anladığını söyle + onay (handon davranışı)
İşe başlamadan, kısa ve net ver:
- **Nottan ne anladım** (1-2 cümle özet — Hedef + nerede kalınmış)
- **Mevcut durum:** branch, uncommitted, açık PR, **staleness verdict** (MISPLACED ise Faz 3'teki **kaynak-çoğaltma redirect satırını** buraya koy)
- **Nasıl devam etmek istiyorum** (3-5 adım, notun ▶ RESUME'undan)
- Sonra: *"Onaylıyor musun, böyle devam edeyim mi?"* — **onay gelene kadar** kod değiştirme / migration / commit / PR YAPMA.

## Faz 5 — Not yoksa (fallback)
- L1 memory `session-state-<branch>.md` (auto-recall) + (varsa) ephemeral dump'tan minimal durum çıkar.
- Hiçbiri yoksa: kullanıcıdan kaldığı yeri netleştirmesini iste — UYDURMA.

## Faz 6 — Onay sonrası: consume (non-destructive)
- Kullanıcı onaylayıp devam edince seçilen notun frontmatter `status: open → consumed` yap (Edit — tek satır; **silme**).
- Commit'i **erteleme** kuralı: bu flip bir sonraki `/devir` commit'ine biner (anında ayrı commit açma). İstenirse küçük `chore(docs): consume <id>` commit'i.
- `consumed` geri-dönülebilir; arşivleme/silme **her zaman kullanıcının manuel kararı**.

---
**Not:** Bu skill `devir`'in yerine geçmez; yeni session'da **devam güvenliği** katmanıdır. SessionStart hook'u compact'te RESUME'u zaten auto-inject eder; bu skill bunu yıkıcı-aksiyon-öncesi onaya bağlar.
