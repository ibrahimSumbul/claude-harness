# devir — Workflow & Tetikleme Haritası

Bu doküman sistemin **çalışma prensibini** anlatır: kullanıcı neyi/ne zaman/nasıl
tetikler, arka planda hangi mekanizma ne zaman ve **neden** çalışır. Tüm değerler
çalışan koddan alınmıştır (dosya:satır referanslı).

> Mimari gerekçeler ve alternatif değerlendirmeleri: [`../skills/devir/DESIGN.md`](../skills/devir/DESIGN.md).

![devir — kim neyi tetikler, arka planda ne çalışır](diagrams/devir-trigger-flow.svg)

*Tek-bakışta özet: solda kullanıcının manuel tetiklediği yol, sağda otomatik L3 hook ağı.
Standalone SVG: [`diagrams/devir-trigger-flow.svg`](diagrams/devir-trigger-flow.svg). Aşağıdaki
Mermaid diyagramlar GitHub'da render olur ve detayı taşır.*

---

## 1. Üç katman, tek cümlede

| Katman | Nedir | Yazıcı | Yer |
|--------|-------|--------|-----|
| **L1** | Global memory (birincil süreklilik) | `/devir` skill | `~/.claude/projects/<proj>/memory/` (git-dışı, makine-local) |
| **L2** | Lokal unique-ID not (opt-in commit ile durable/cross-machine) | `/devir` skill | `<repo>/.claude/docs/devir-notes/<id>.md` (varsayılan **lokal**; opt-in commit) |
| **L3** | Hook güvenlik ağı (advisory; model işbirliği gerektirmez) | deterministik | `~/.claude/hooks/devir-*.py` |

**Tasarım ilkesi:** L1 tek-session sürekliliğini tek başına çözer; L2 yalnızca
*cross-machine taşıma* ve *paralel-branch ayrıştırma* için hak ediyor. Bu yüzden L2 notu
**varsayılan olarak commit EDİLMEZ** (solo tek-makinede L1 yeterli; public repo'da iç-state
sızıntısı) — git'e girmesi **opt-in** (`git add -f`). L3, kullanıcı/model manuel `/devir`'i
kaçırırsa devreye giren ağdır — **zorlayıcı değil, advisory**.

---

## 2. Mimari

```mermaid
flowchart TB
    subgraph L1["L1 — Global Memory (PRIMARY, git-disi)"]
      direction TB
      M1["session-state-(branch).md<br/>branch-keyed"]
      M2["MEMORY.md index<br/>her session auto-recall"]
    end
    subgraph L2["L2 — Git-tracked Notlar (durable)"]
      N1["(repo)/.claude/docs/devir-notes/(id).md<br/>status: draft / open / consumed / superseded"]
    end
    subgraph L3["L3 — Hook Guvenlik Agi (advisory, fail-safe)"]
      direction TB
      H1["devir-autotrigger.py<br/>UserPromptSubmit · 260k nudge"]
      H2["devir-precompact.py<br/>PreCompact · dump + draft"]
      H3["devir-sessionstart.py<br/>SessionStart · inject / banner"]
    end
    SKILL["/devir skill<br/>(kullanici-manuel)"] -->|yazar| L1
    SKILL -->|yazar| L2
    RESUME["/devir-resume skill<br/>(kullanici-manuel)"] -->|okur + consume| L2
    RESUME -->|fallback okur| L1
    H2 -->|mekanik draft| L2
    H3 -->|RESUME oku| L2
    COMMON["devir_common.py · devir_memory.py<br/>(paylasilan lib)"] -.-> L3
    COMMON -.->|flock upsert| M2
```

L1+L2'yi **model** (skill) yazar; L3 **deterministik** çalışır (model uymasa bile).

---

## 3. Tam yaşam döngüsü (uçtan uca)

```mermaid
flowchart TD
    A["Kullanici: /devir<br/>(~260k token, manuel)"] --> B["Faz 1 · canli git state<br/>git status / log / pnpm test (verbatim)"]
    B --> C["Faz 2 · in-flight + ✗ denenen/basarisiz + kararlar<br/>(en kritik: siradaki TAM adim)"]
    C --> D["Faz 3 · L1 memory<br/>session-state + MEMORY.md flock upsert"]
    D --> E["Faz 5 · L2 not<br/>PROMOTION GATE → open / draft"]
    E --> F["Faz 6 · verbatim handoff blogu (ekrana)"]
    F --> G["Faz 7 · not LOKAL (varsayilan); commit OPT-IN<br/>(cross-machine/takim → onay + git add -f, AI trailer yok)"]
    G --> H["▶ YENI SESSION ac"]
    H --> I{"SessionStart<br/>source?"}
    I -->|startup / resume| J["banner: N acik not<br/>1 → RESUME ozeti · ≥2 → SOR"]
    I -->|compact| K["RESUME auto-inject<br/>(insan-yok recovery)"]
    I -->|clear| Z["no-op"]
    J --> L["/devir-resume (veya 'resume')"]
    K --> L
    L --> M{"Faz 3 · staleness<br/>git-drift"}
    M -->|0 commit, ayni branch| FR["FRESH"]
    M -->|1-2 commit| SS["SLIGHTLY STALE"]
    M -->|≥3 / branch degisti / drift bilinmiyor| ST["STALE → once dogrula"]
    FR --> N["Faz 4 · 'ne anladim' + plan + ONAY"]
    SS --> N
    ST --> N
    N --> O["devir-resume Faz 6 · consume: open → consumed<br/>(geri-donulebilir, silmez)"]
```

> Diyagram yüksek-seviye: **Faz 4 (CLAUDE.md, ikincil — varsa)** sadeleştirme için elendi;
> kritik state zaten Faz 3'te L1'de. Faz numaraları iki ayrı skill'e ait — `/devir` yazar
> (Faz 0-7), `/devir-resume` okur/consume eder (Faz 1-6).

**Yazma etkisi (özet):** L1 (session-state + topic dosyaları) + L2 (`<id>.md`) yazılır →
`MEMORY.md` flock-upsert → git commit kapanışı → kullanıcı **fresh session** açar.

---

## 4. Tetik tablosu (A) — KULLANICI TETİKLER

| Kullanıcı ne yapar | Ne çalışır | Ne zaman / koşul |
|--------------------|-----------|------------------|
| `/devir` yazar | `devir` skill (Faz 0-8: state yakala → L1+L2 → handoff → commit) | İstendiğinde, ~260k civarı. Model **otomatik çağıramaz** (`disable-model-invocation: true`). |
| `/devir-resume` (veya "resume", "kaldığımız yerden devam", "hand on") | `devir-resume` skill (not seç → staleness → özet → çoklu ise SOR → onayla → uygula) | Fresh session başında, devam etmek için. Manuel-only. |
| Herhangi bir prompt gönderir | `devir-autotrigger.py` (UserPromptSubmit) önce çalışır | Her prompt; yalnızca transcript ≥260k ise ve refire penceresi izin veriyorsa nudge enjekte eder. |
| `/compact` (manuel compaction) | `devir-precompact.py` (`trigger=manual`) → sonra `devir-sessionstart.py` (`source=compact`) | Manuel compaction'da: dump + draft yazılır, sonra RESUME geri enjekte edilir. |
| Model-invocable skill çağırır (`/code-review`, `/simplify`, `/verify`, …) | İlgili skill | İsimle veya modelin trigger eşleşmesiyle (devir-dışı skill'ler). |

## 5. Tetik tablosu (B) — ARKA PLANDA OTOMATİK

| Olay | Mekanizma | Ne zaman | Neden |
|------|-----------|----------|-------|
| Token ~260k'yı aşar | `devir-autotrigger.py` (UserPromptSubmit) `additionalContext` enjekte eder | Prompt'ta, transcript ≥260k ve bu session'da daha önce ateşlenmediyse (veya +20k birikti) | ~300k degradation bölgesinden önce temiz `/devir` devri öner. **Advisory — skill'i zorlayamaz** (Anthropic #43733). |
| Compaction başlamak üzere | `devir-precompact.py` (PreCompact) | Her compaction'dan hemen önce | Model işbirliği **gerekmeden** canlı git state'i koru: her zaman ephemeral dump + (repo varsa & `open` not yoksa) git-tracked **draft** not. Advisory nudge'ın boşluğunu kapatır. |
| Compaction sonrası yeni context | `devir-sessionstart.py` (`source=compact`) | Compaction fresh context üretince | İnsan-yok recovery: en iyi notun `▶ RESUME`'unu auto-inject (yoksa ephemeral dump). Çoklu branch açık not varsa **otomatik seçmez**, `/devir-resume` der. |
| Session startup / resume | `devir-sessionstart.py` (`source=startup`/`resume`) | Session başlar/devam ederken (`clear` değil) | Durum banner'ı: worktree için açık not sayısı. 1 → RESUME özeti + `/devir-resume` öner; ≥2 → **SOR** (sessizce seçmez/consume etmez). |
| Her session (bu proje) | Auto-memory recall (hook değil — harness özelliği) | Session başında | `MEMORY.md` index context'e enjekte; tekil memory dosyaları alaka ile okunur. **Birincil (L1) süreklilik.** |
| Eski marker birikimi | `cleanup_old_markers()` (autotrigger içinde) | Bir UserPromptSubmit ateşlemesine binerek | `.devir-state/`'te 7 günden eski `.fired`/`.consumed.md`/`.dump.md` marker'larını sil → sınırsız büyümesin. |

> **Yan yana koşan, devir-dışı hook'lar:** Aynı `settings.json`'da başka sistemlere ait
> devir-dışı hook'lar (ör. `SessionStart` / `Stop` / `PostToolUse`'a bağlı bir telemetri)
> bulunabilir. Bunlar devir ile ilgisizdir, context enjekte etmez ve bu repoya
> vendor'lanmamıştır; yalnızca `SessionStart` event'ini devir ile paylaştıkları için
> burada not edilir (settings birleştirirken üzerine yazılmamalı).

---

## 6. Tetik akışı (güvenlik ağı zaman çizgisi)

```mermaid
sequenceDiagram
    autonumber
    participant U as Kullanici
    participant CC as Claude Code (model)
    participant H as devir L3 hooks
    participant FS as Kalici katman (L1/L2 + dump)

    U->>CC: prompt
    CC->>H: UserPromptSubmit
    Note over H: tokens >= 260k?
    H-->>CC: evet → "once /devir calistir" (advisory)
    Note over CC: model uyabilir / uymayabilir
    CC->>H: PreCompact (compaction oncesi)
    H->>FS: ephemeral dump (her zaman) + draft not (repo & open-yok)
    Note over CC,FS: --- compaction → yeni context ---
    CC->>H: SessionStart(source=compact)
    H->>FS: en iyi notu oku
    H-->>CC: ▶ RESUME auto-inject (INJECT_CAP=1400)
    Note over U,CC: yikici aksiyon oncesi /devir-resume ile onay
```

---

## 7. Bileşen bazında: trigger · ne zaman · neden

| Bileşen | Trigger tipi | Ne zaman | Neden var |
|---------|-------------|----------|-----------|
| `/devir` skill | **kullanıcı-manuel** (`disable-model-invocation: true`) | ~260k'da elle | Yüksek-fidelity flush. Yalnız model gerçek "sıradaki adım"ı, denenen/başarısız ve kararları üretebilir. |
| `/devir-resume` skill | **kullanıcı-manuel** | Fresh session başı | Güvenli devam: doğru notu seç, anladığını doğrula, belirsizlikte SOR, yıkıcı aksiyon öncesi onay. |
| `devir-autotrigger.py` | **hook: UserPromptSubmit** | tokens ≥ 260k & refire izinli | Degradation öncesi advisory nudge. Zorlayamaz → deterministik ağ ayrı. |
| `devir-precompact.py` | **hook: PreCompact** (`manual`/`auto`) | Compaction'dan hemen önce | İşbirliği gerekmeden mekanik yakalama: dump (her zaman) + draft (repo & open-yok). Her hata → exit 0 (compaction'ı kırmaz). |
| `devir-sessionstart.py` | **hook: SessionStart** (`source`-keyed) | Yeni context | `compact`→RESUME inject; `startup`/`resume`→banner; `clear`→no-op. |
| `devir_common.py` | (kütüphane) | 3 hook import eder | Defensive paylaşılan: token tahmini, git, not tarama/precedence, redaction, worktree-match. |
| `devir_memory.py` | **kullanıcı-manuel** (Faz 3'ten çağrılır) | MEMORY.md index upsert | flock + atomik + idempotent (paralel-session race koruması). |

---

## 8. Sabitler / eşikler (koddan)

| Sabit | Değer | Kaynak | Anlam |
|-------|-------|--------|-------|
| `THRESHOLD` | `260_000` | `autotrigger.py:18` | `/devir` tetik eşiği (~300k degradation öncesi; gözlem: 282k spike) |
| `REFIRE_GAP` | `20_000` | `autotrigger.py:19` | İlk nudge yok sayılırsa +20k token sonra tekrar (anti-nag) |
| `CLEANUP_DAYS` | `7` | `autotrigger.py:20` | `.devir-state` marker temizliği |
| `NOTE_FRESH_HOURS` | `6` | `autotrigger.py:21` | Bu süre içinde taze not yoksa "not oluştur" hatırlat |
| `INJECT_CAP` | `1_400` | `sessionstart.py:23` | Enjekte edilen `additionalContext` max karakter |
| `STATUS_RANK` | `{draft:0, open:1, consumed:2, superseded:-1}` | `devir_common.py:25` | Resume precedence |
| `DEFAULT/WIDE_WINDOW` | `262_144` / `1_048_576` | `devir_common.py:17-18` | Transcript kuyruk okuma penceresi |
| `--max-lines` | `200` | `devir_memory.py:126` | Index ≤200 satır (her session yüklenir); uyarır, sessizce kesmez |

**Token tahmini notu:** `latest_usage_tokens()` **son** usage satırını alır (max değil) →
compaction sonrası eski yüksek değerle mis-fire/şişme olmaz (`devir_common.py:224-248`).

---

## 9. Tasarım kararları (neden böyle?)

- **Advisory, gate değil.** Hook bir shell komutu; modeli zorla skill çalıştıramaz
  (Anthropic #43733). Bilinçli "BEHIND" konum — enforcement platform-limitli, bu yüzden
  deterministik ağ (precompact + sessionstart) ayrı ve best-effort. Her hook her hatada
  exit 0 → asla compaction/prompt kırmaz.
- **Non-destructive.** Stale fact düzeltilir, göreli→mutlak tarih; merge/delete YOK →
  adaylar `⚠ Reconcile`'a, riskli kısım fresh session'da `/consolidate-memory`. `consumed`
  geri-dönülebilir flip; silme her zaman kullanıcı kararı.
- **flock + atomik + idempotent index.** `MEMORY.md` tek paylaşımlı, git-dışı dosya →
  gerçek paralel-session race. `devir_memory.py` read-modify-write'ı `flock` ile serialize
  eder, temp+`os.replace` ile atomik yazar, key-bazlı idempotent upsert yapar (duplicate yok).
  Multi-line `--line` reddedilir; `--max-lines` aşılırsa uyarır, sessizce **truncate etmez**.
- **Secret redaction (opt-in raw).** Ham mesaj yakalama default KAPALI (gizlilik); redaction
  her zaman açık. `last_messages()` **cap'ten ÖNCE** tam metni redact eder → sınır-aşan secret
  sızmaz. Pattern seti: env/key-value, bearer, provider prefix'leri (sk/ghp/xox…/sbp/glpat),
  AWS AKIA, Google AIza, JWT, URL-gömülü cred, PEM blokları.
- **Fence-aware section extraction.** `extract_section()` ` ``` ` fence takip eder: fence
  içindeki `#` markdown başlık değil, shell yorumudur → RESUME'un `# İlk aksiyon:` satırını
  kesmez. (Bu, E2E test sırasında bulunup düzeltilen gerçek bir prod bug'ıydı.)
- **Promotion gate.** Not yalnızca checklist self-validate'ten geçince `open`'a yükselir
  (Hedef / literal RESUME / non-empty denenen / kararlar / `[TODO]` yok); aksi halde `draft`.
- **Staleness ref-guard.** `covers_since` gerçek commit ref mi diye `^{commit}` ile doğrulanır;
  note-id / "session start" ref değildir → 0-drift sanılmaz; başarısız git komutu "drift
  bilinmiyor" (→STALE) olur, asla yutulup FRESH sanılmaz.
- **Worktree/branch-keyed izolasyon.** L1 branch-keyed (paralel branch'ler ayrı dosya);
  L2 unique-ID dosyalar (merge'de additive, çakışmasız). Resume/banner'da **worktree-match
  birincil filtre** (`under_worktree` realpath-normalize → `/var↔/private/var` symlink'i atlar).
