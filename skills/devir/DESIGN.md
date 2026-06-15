# devir skill — DESIGN & EVOLUTION

> Bu doc: skill'in **mimarisi**, **paralel-session conflict tasarımı**, **dış-dünya benchmark konumu**
> ve **evrimi (önceki → şimdiki → geliştirilecek)**. Operasyonel adımlar `SKILL.md`'de; bu doc *neden*'i tutar.
> Eşlik eden skill: `../devir-resume/SKILL.md` (fresh session'da güvenli devam = handon).
> Eşlik eden skill: `../devir-land/SKILL.md` (context sınırından ÖNCE biten kapalı dilimi aynı session'da indir = land; bkz. §8).

---

## 1. Amaç

Context, long-context degradation bölgesine (~300k) girmeden **çalışma state'ini kalıcı katmanlara flush et → fresh session aç**.
Manuel `/devir` birincil yol; hook'lar advisory güvenlik ağı. (memory: `keep-context-bounded-quality`)

---

## 2. Mimari — 3 katman

| Katman | Ne | Konum | Rol |
|---|---|---|---|
| **L1 — Global memory** | `session-state-<branch>.md` | `~/.claude/projects/<proje>/memory/` (git **dışı**, makine-local, proje+branch-keyed) | **BİRİNCİL süreklilik** — auto-recall ile her session yüklenir |
| **L2 — Lokal not (opt-in commit)** | `<repo>/.claude/docs/devir-notes/<id>.md` | repo içi, **varsayılan git-ignored** (global ignore), proje-bazlı | **Durable + cross-machine** — yalnız **opt-in commit** (`git add -f`) ile (push ile taşınır); varsayılan lokal |
| **L3 — Hook ağı** | autotrigger / precompact / sessionstart | `~/.claude/hooks/` (global `settings.json`) | **Advisory** nudge + mekanik draft + restore |

**İlke:** L1 tek-session sürekliliğini zaten çözer. L2 yalnız iki durumda hak eder: **cross-machine** ve **paralel-branch disambiguation**.
Bu yüzden L2 notu **varsayılan olarak commit EDİLMEZ** — solo tek-makinede L1 yeterli, public repo'da commit iç-state sızdırır. Git'e girmesi **opt-in**: not dizini global gitignore'da; commit gerektiğinde `git add -f` ile (Faz 7). Lokal dosya + hook/resume tarama gitignore'dan **etkilenmez** (`scan_notes` dosya sistemini okur, git'i değil).
Skill **global** (tüm projelerde), notlar **proje-bazlı** (repo-göreli yol → `project-a`'da resume, `project-b`'nin notunu görmez).

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

## 7. `/devir-land` — bitmiş dilimin tümleyeni

`/devir` ile aynı aileden, ama **karşıt yönde** çalışır. İkisi context boundary'nin iki tarafını kapatır:

| | `/devir` | `/devir-land` |
|---|---|---|
| Tetik | Yarım iş ~260k sınırına **çarptı** | Kapalı dilim sınırdan **ÖNCE bitti** |
| Süreklilik | L1 memory + L2 not + handoff bloğu | **YOK** — not yazmaz, memory'ye dokunmaz |
| Session | **fresh session** aç | **AYNI session**'da kal |
| Eylem | state'i kalıcı katmana flush | dilimi ilgili PR/branch'e commit + push |

**Neden ayrı skill (not yeniden-kullanım değil):** `/devir`'in özü *gelecek session için yüksek-fidelity state yazmak*. `/devir-land`'in özü *biten işi paylaşılan history'ye güvenle entegre etmek*. İlki yazma/recall problemi, ikincisi merge/concurrency problemi. Tek skill'e sıkıştırmak ikisinin de gate'ini bulandırırdı.

**Süreklilik kararı (no-note / no-memory):** dilim DONE → gelecek session'a aktarılacak "nerede kalındı" yok. Bu yüzden `/devir-land` L1 `session-state` yazmaz, `devir_memory.py upsert` çağırmaz, L2 not üretmez/consume/flip etmez. Saf entegrasyon. (Branch'in açık notu varsa ve dilim onu bitiriyorsa → kullanıcıya yalnızca `/devir-resume` consume / manuel flip **önerir**; skill nota dokunmaz.) Bu, §3 not yaşam döngüsünü `/devir-land`'in **kasıtlı olarak es geçtiği** anlamına gelir.

**DONE GATE** (`/devir`'in promotion-gate'inin land-analoğu): land etmeden ÖNCE dilimin gerçekten bittiği mekanik kanıtlanır — half-edit yok · `[TODO]` taraması temiz · kod değiştiyse `pnpm test:run` + `tsc --noEmit` **verbatim** geçer · dilim kendi içinde kapalı. Geçmezse → `/devir`'e yönlendir (land yarım iş için değil).

**Conflict tasarımı — conservative + Opus-supervised escalation (§4'ün uzantısı):**
- **Default conservative:** cerrahi pathspec (asla `-A`/`-u`), fetch + rebase-before-push, **force-push YOK**, pushed commit'e history-rewrite YOK, non-fast-forward'da **retry-once**.
- **Çakışma/divergence'ta kör çözme YOK, kör sorma YOK:** önce mekanik bağlam topla → **Opus supervisor subagent** (READ-ONLY analiz, hiç yazmaz) → verdict (`SIMPLE/MEDIUM/HIGH/UNCERTAIN` + `foreign_involved` + `foreign_work_dropped`).
- **Verdict kapısı:** SIMPLE **ve** çatışma yalnız kendi dilim dosyalarında (MINE) **ve** additive/mekanik **ve** yabancı iş düşmüyor → uygula + devam + **raporla (ham hata dahil)**. Aksi halde (MEDIUM+/UNCERTAIN, **herhangi bir FOREIGN dosya**, yabancı-iş-düşürme riski) → analiz + seçenekleri sun, **açık onay bekle**. Foreign-file conflict ne kadar "basit" görünse de **HER ZAMAN** escalate eder.
- **Single-writer (§4a ile uyum):** subagent yalnız öneri üretir (geri-alınabilir); **tek yazıcı = ana skill** (atomik, denetlenebilir). İki yazıcı paylaşılan worktree'de race + geri-alınamaz yabancı-hunk kaybı doğururdu.

**Paralel & skalar session zarar-vermezlik garantisi:** paralel = diğer eşzamanlı worktree/branch session'ları; skalar = bu tek lineer timeline. Garanti mekanizmaları: cerrahi pathspec (yalnız dilim dosyaları) · additive (asla destructive) entegrasyon · force-push YOK · `-A`/`-u` YOK · rebase YALNIZ local-unpushed commit'lere (`@{u}..@`) · yabancı hunk asla atılmaz · paylaşımlı tek-dosya index'e (gerekirse) yalnız `devir_memory.py` flock-helper ile yazılır (varsayılan: hiç dokunulmaz).

---

## 8. Versiyon tablosu

| v | Tarih | Değişiklik |
|---|---|---|
| 1.0 | (öncesi) | 5 faz, memory+CLAUDE.md, 270k advisory + mekanik dump. Kalıcı not/ID/commit yok. |
| **2.0** | 2026-06-13 | **Unique-ID git-tracked not** (`.claude/docs/devir-notes/`) + draft→open→consumed lifecycle + **260k** + commit kapanışı (trailer'sız) + MEMORY.md `flock` tam-fix + **`/devir-resume`** (staleness + ask-on-ambiguity) + redaction/opt-in raw + SessionStart auto-inject & banner. Benchmark-driven (landscape survey) + 13-bulgu adversarial-review hardening (genişletilmiş redaction patternleri, staleness ref-guard, token "son-kazanır", concurrency edge-case'leri). |
| **2.1** | 2026-06-14 | **`/devir-land`** — bitmiş-dilim tümleyeni (§7): aynı session'da kapalı dilimi (döküman + plan + ilgili PR/branch kodu) commit + push ile indir. DONE GATE (test+tsc verbatim) · cerrahi pathspec (asla `-A`/`-u`) · fetch + rebase-before-push (force YOK, retry-once) · conservative + **Opus supervisor subagent** conflict gate (SIMPLE & kendi-territory & additive → uygula+raporla; aksi/FOREIGN → onay bekle). Not/memory'ye dokunmaz (süreklilik YOK); single-writer = ana skill; paralel & skalar session zarar-vermezlik garantisi. |
| **2.2** | 2026-06-15 | **L2 not lokal-varsayılan + commit opt-in** (§2, Faz 7). Devir tüm projelerde kullanıldığından varsayılan değişti: not artık **commit EDİLMEZ** (solo tek-makinede L1 yeterli; public repo'da iç-state sızıntısı). Mekanizma: not dizini (`.claude/docs/devir-notes/`) **global gitignore**'da → opt-in commit `git add -f` ile (yalnız cross-machine/takım). `scan_notes` dosya sistemini okuduğundan resume/hook/e2e **etkilenmez**. Repo bir **etiketli örnek** notu (`archive/`) tracked tutar; gerçek session notları lokal kalır. |
