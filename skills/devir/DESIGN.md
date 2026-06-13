# devir skill — DESIGN & EVOLUTION

> Bu doc: skill'in **mimarisi**, **paralel-session conflict tasarımı**, **dış-dünya benchmark konumu**
> ve **evrimi (önceki → şimdiki → geliştirilecek)**. Operasyonel adımlar `SKILL.md`'de; bu doc *neden*'i tutar.
> Eşlik eden skill: `../devir-resume/SKILL.md` (fresh session'da güvenli devam = handon).

---

## 1. Amaç

Context, long-context degradation bölgesine (~300k) girmeden **çalışma state'ini kalıcı katmanlara flush et → fresh session aç**.
Manuel `/devir` birincil yol; hook'lar advisory güvenlik ağı. (memory: `keep-context-bounded-quality`)

---

## 2. Mimari — 3 katman

| Katman | Ne | Konum | Rol |
|---|---|---|---|
| **L1 — Global memory** | `session-state-<branch>.md` | `~/.claude/projects/<proje>/memory/` (git **dışı**, makine-local, proje+branch-keyed) | **BİRİNCİL süreklilik** — auto-recall ile her session yüklenir |
| **L2 — Git-tracked not** | `<repo>/.claude/docs/devir-notes/<id>.md` | repo içi, git-tracked, **proje-bazlı** | **Durable + cross-machine** (push ile taşınır) |
| **L3 — Hook ağı** | autotrigger / precompact / sessionstart | `~/.claude/hooks/` (global `settings.json`) | **Advisory** nudge + mekanik draft + restore |

**İlke:** L1 tek-session sürekliliğini zaten çözer. L2 yalnız iki durumda hak eder: **cross-machine** ve **paralel-branch disambiguation**.
Skill **global** (tüm projelerde), notlar **proje-bazlı** (repo-göreli yol → `project-b`'de resume, `project-a`'in notunu görmez).

---

## 3. Not yaşam döngüsü

```
draft  → open → consumed
(mekanik)(temiz)(devam edildi)
```

| Statü | Kim yazar | Anlam | Resume davranışı |
|---|---|---|---|
| `draft` | PreCompact hook (mekanik) | auto-compact oldu, model /devir çalıştırmadı — RESUME yok | "öneri/tamamla" gösterir; `open` varsa **superseded** |
| `open` | `/devir` skill (temiz) | gerçek handoff, RESUME satırı dolu | resume'un birincil hedefi |
| `consumed` | `/devir-resume` (onayında) | bu nottan devam edildi | varsayılan listeden düşer; **flip geri-dönülebilir** |

- **Supersession:** aynı branch/worktree için yeni `open`, eski `draft`/`open` notu `status: superseded` yapar (silmez; scan'de düşer, resume `open`'ı tercih eder).
- **Non-destructive:** resume hiçbir şeyi **silmez**; `consumed` sadece frontmatter flip'i (geri alınabilir). Silme/arşivleme **her zaman manuel**. Arşiv: `devir-notes/archive/` (scan oraya bakmaz).

### Not formatı

Dosya: `<YYYY-MM-DD>-<branch-slug>-<rand6>.md` (ör. `2026-06-13-feat-hr-ats-a3f9c1.md`).
ID değişmez **provenance**; seçim mantığı dosya adından değil **frontmatter**'dan okunur:

```yaml
---
id: 2026-06-13-feat-hr-ats-a3f9c1
session_id: <varsa>
branch: feat/hr-ats
worktree: /abs/repo/path
created: 2026-06-13T14:30:00+03:00
status: open          # draft | open | consumed | superseded
tokens: 261000
covers_since: <önceki not id / commit sha>   # incremental pencere
---
```

Zorunlu bölümler (promotion gate — `open` için): **Hedef · Yapılan · Denenen/başarısız (kronolojik + tam hata) · Kararlar (seçilen VE reddedilen) · ▶ RESUME (literal komut bloğu)**.

---

## 4. Paralel-session conflict tasarımı

İki ayrı problem:

**(a) Yazma anı — clobber**
- **L2 notlar:** unique-id → her session kendi dosyası → branch merge'de additive, **conflict yok**.
- **L1 `session-state-<branch>`:** branch-keyed → paralel branch'ler ayrı dosya.
- **MEMORY.md index (tek paylaşımlı dosya, git değil):** asıl race. **Tam fix:** `devir_memory.py` → `flock` (read-modify-write serialize) + atomik `os.replace` (torn-file yok) + **idempotent branch-keyed upsert** (duplicate yok). Skill index'i bununla yazar, elle Edit etmez.

**(b) Resume anı — seçim**
```
notlar = status in (open, draft), archive hariç (frontmatter scan)
here = cwd, note.worktree altındaysa            ← BİRİNCİL filtre
  0 → L1 memory session-state → ephemeral dump → kullanıcıya sor
  1 → staleness check → özet+plan → onay → consumed
  ≥2 → branch-match tiebreak; hâlâ ≥2 ise NUMARALI LİSTE + "hangisi?" SOR  ← sessizce seçme
worktree-match boşsa repo'daki tüm open notlara genişle + sor
```
**Branch rename / yeni-branch:** worktree-match birincil olduğundan not branch değişse de bulunur; yeni branch'te sonraki `/devir` yeni `session-state-<yeni-branch>` doğurur.

---

## 5. Benchmark — landscape'e göre konumumuz

40+ gerçek araç tarandı (workflow `handoff-skill-landscape`, 2026-06-13). Boyut-boyut verdict:

| Boyut | Verdict | Not |
|---|---|---|
| Persistence (3 katman) | **AHEAD** | çoğu tek katman; DB'siz cross-machine ayrımı nadir |
| **Parallel-conflict** | **AHEAD** | skill katmanının tamamı "none documented"; çözüm sadece DB/runtime'da (Continuous-Claude `file_claims`, ai-memory single-writer, rjmurillo `O_CREAT\|O_EXCL`) — biz DB'siz flock+atomic |
| Privacy/redaction | **AHEAD** | alanın neredeyse hiçbirinde yok; sadece softaworks + agent-chorus |
| **Lifecycle (draft→open→consumed)** | **NOVEL** | survey'deki tek özgün katkı — kimse notu maturity ile modellemiyor |
| Trigger · Unique-ID · Resume/handon | PARITY | sağlam ama yaygın |
| Hooks/enforcement | BEHIND *(kasıtlı)* | advisory; Anthropic #43733 PreCompact'in modeli zorlayamadığını teyit → enforcement zaten platform-limitli |

Karşılaştırılan temsilciler: REMvisual/claude-handoff, sofumel/claude-handoff-revive, who96/claude-code-context-handoff,
thepushkarp/handoff, chadthornton/reheat, softaworks/session-handoff, petekp/catch-up, Cline & Roo Memory Bank,
rjmurillo/ai-agents, parcadei/Continuous-Claude-v3, akitaonrails/ai-memory, BMad-Method, Spec-Kit, claude-task-master, Kiro,
OpenAI Agents SDK, LangGraph, AutoGen, cote-star/agent-chorus, AICTX.

---

## 6. Evrim

### 6.1 — v1 (ÖNCEKİ)

- 5 faz; memory birincil + CLAUDE.md ikincil; **kalıcı not YOK, unique-ID YOK, commit kapanışı YOK**.
- Hook: autotrigger **270k** advisory; precompact mekanik dump (`~/.claude/.devir-state/<id>.dump.md`, **redaction yok**, ham mesaj her zaman); sessionstart tek-dump restore.
- Resume: ayrı skill yok; memory auto-load + dump pointer'a güven.
- Doc drift: SKILL.md "~150k/170k" derken kod 270k.

### 6.2 — v2 (ŞİMDİKİ KARARLAR + GELİŞTİRİLECEK)

**A. Brainstorm kararları (kilitli):**
1. Eşik **270k → 260k** (advisory; ~300k degradation öncesi, 282k gözlem spike'ından önce).
2. **Unique-ID not** `<date>-<branch>-<rand6>` + zengin frontmatter.
3. **Git commit kapanışı** — AI co-author trailer **YOK** (kullanıcı tercihi), onay zorunlu, main'de `chore/devir-*` branch öner.
4. **Paralel-conflict:** L2 unique-id + MEMORY.md `flock`+atomik+idempotent upsert (tam fix) + resume'da belirsizlikte **SOR**.
5. **`/devir-resume`** skill'i (handon): özet + çok-seçenekte SOR + onay + non-destructive.
6. **Cherry-pick (Cursor):** redaction + opt-in raw + session-token fallback + NOT2U; **gate YOK** (advisory); bug kopyalanmaz, Claude I/O'ya uyarlanır.
7. Konum **`.claude/docs/devir-notes/`** (proje docs'unu kirletmez); consume **ertelenir** (sonraki devir commit'ine biner).

**B. Benchmark bundle (MUST 1-5 + SHOULD 6-8):**
1. **Zorunlu "Denenen/başarısız yollar" + "Seçilen VE reddedilen kararlar"** (REMvisual/reheat/softaworks) — en yüksek değerli içerik.
2. **draft→open promotion gate** — skill içi self-validation checklist (thepushkarp Stop-gate'in advisory karşılığı).
3. **Resume'da staleness check** — git-drift (commit/dosya/divergence) → `FRESH/STALE` (softaworks `check_staleness`).
4. **SessionStart(compact)'ta RESUME auto-inject** — insan-yok compaction anında hands-free recovery (thepushkarp/who96/ai-memory).
5. **Idempotent non-regressing precedence** — `draft<open<consumed`; resume `open`'ı `draft`'a tercih eder, geç `draft` `open`'ı ezemez (BMad). *(unique-id dosyalar zaten file-clobber'ı önlediğinden read-time precedence olarak uygulanır.)*
6. **RESUME = literal copy-paste komut bloğu** (REMvisual Quick Start / thepushkarp) — hook'suz fallback.
7. **PreCompact draft'ta mekanik ground-truth** — tool-input'lardan dokunulan dosyalar + `git status` + last-N mesaj (who96).
8. **SessionStart durum banner'ı** — `DEVIR: <branch> için open not var (<id>)` / `yok` (Roo `[MEMORY BANK: ACTIVE]`).

**C. LATER (defer):** map-reduce capture (500k+; biz 260k'da flush'lıyoruz), `/devir-quick` modu, evidence-bearing checklist items (rjmurillo), reconstruct-from-git self-healing.

---

## 7. Versiyon tablosu

| v | Tarih | Değişiklik |
|---|---|---|
| 1.0 | (öncesi) | 5 faz, memory+CLAUDE.md, 270k advisory + mekanik dump. Kalıcı not/ID/commit yok. |
| **2.0** | 2026-06-13 | **Unique-ID git-tracked not** (`.claude/docs/devir-notes/`) + draft→open→consumed lifecycle + **260k** + commit kapanışı (trailer'sız) + MEMORY.md `flock` tam-fix + **`/devir-resume`** (staleness + ask-on-ambiguity) + redaction/opt-in raw + SessionStart auto-inject & banner. Benchmark-driven (landscape survey) + 13-bulgu adversarial-review hardening (genişletilmiş redaction patternleri, staleness ref-guard, token "son-kazanır", concurrency edge-case'leri). |
