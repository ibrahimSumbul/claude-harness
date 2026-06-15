# claude-harness

[English](README.md) · **Türkçe**

**Claude Code için session devir-teslim (context-flush) sistemi.** Uzun-context
degradasyonu (~300k token) başlamadan önce çalışan session'ın state'ini yüksek-fidelity
kalıcı katmanlara yazar, temiz bir session'a geçmeyi ve oradan **güvenli devam**ı sağlar.

> `devir` (TR): bir işin/görevin başkasına veya bir sonrakine teslim edilmesi.

![devir — kim neyi tetikler, arka planda ne çalışır](docs/diagrams/devir-trigger-flow.svg)

*Tek bakışta: solda Session A'dan ayrılan `/devir-land` kolu (bitmiş dilim), ortada manuel
`/devir` → yeni session → `/devir-resume` yolu, sağda otomatik L3 hook ağı.*

---

## Neden

Tek bir Claude Code session'ı büyüdükçe (~300k civarı) cevap kalitesi düşmeye başlar; devir bunu **~260k'da**, degradation bölgesine girmeden önce yakalar.
"Yeni session aç" demek kolay ama **bağlam kaybolur**: nerede kalındığı, neyin denenip
başarısız olduğu, hangi kararların neden alındığı. `devir` bu state'i üç katmana yazar →
yeni session sıfırdan değil, **kaldığı yerden** devam eder.

## Mimari — üç katman

| Katman | Nedir | Nerede yaşar | Rol |
|--------|-------|--------------|-----|
| **L1** | Global memory (birincil) | `~/.claude/.../memory/` | Makine-local süreklilik; her session'a auto-recall |
| **L2** | Lokal unique-ID not (opt-in commit) | `<repo>/.claude/docs/devir-notes/<id>.md` | Varsayılan **lokal** (global gitignore'da); **opt-in commit** (`git add -f`) ile durable / cross-machine / takım-paylaşımlı |
| **L3** | Hook güvenlik ağı | `~/.claude/hooks/devir-*.py` | Model işbirliği gerekmeden mekanik yakalama/restore (advisory) |

L1 + L2'yi **model** (skill) yazar; L3 **deterministik** çalışır (model uymasa bile).

## Bileşenler

**Skills** (`disable-model-invocation: true` — yalnızca kullanıcı tetikler):
- [`skills/devir/SKILL.md`](skills/devir/SKILL.md) — manuel `/devir`: canlı git state yakala → L1+L2 yaz → handoff bloğu → **opt-in** commit kapanışı (varsayılan: not lokal kalır; commit yalnız cross-machine/takım için; Faz 0-8). Mimari gerekçeler: [`skills/devir/DESIGN.md`](skills/devir/DESIGN.md).
- [`skills/devir-resume/SKILL.md`](skills/devir-resume/SKILL.md) — `/devir-resume`: yeni session'da not seç → staleness (git-drift) kontrolü → ne anladığını söyle → **onay al** → devam.
- [`skills/devir-land/SKILL.md`](skills/devir-land/SKILL.md) — `/devir-land`: bitmiş, kendi içinde kapalı dilimi **aynı session'da** indir → DONE GATE (test+tsc verbatim) → cerrahi pathspec staging → trailer'sız commit → fetch + rebase-before-push (force YOK) → çakışmada Opus supervisor subagent + onay kapısı (Faz 0-6). Not/memory'ye dokunmaz (süreklilik yok); `/devir`'in bitmiş-dilim tümleyeni. Mimari gerekçeler: [`skills/devir/DESIGN.md`](skills/devir/DESIGN.md).

**Hooks** (L3, hepsi defensive: her hata → exit 0, asla session/compaction kırmaz):
- [`hooks/devir-autotrigger.py`](hooks/devir-autotrigger.py) — `UserPromptSubmit`: ~260k token eşiğinde `/devir` çalıştırmayı önerir (advisory nudge + refire guard).
- [`hooks/devir-precompact.py`](hooks/devir-precompact.py) — `PreCompact`: compaction'dan hemen önce mekanik state dump + git-tracked `draft` not (redaction'lı).
- [`hooks/devir-sessionstart.py`](hooks/devir-sessionstart.py) — `SessionStart`: `compact`'te RESUME auto-inject; `startup`/`resume`'da durum banner'ı.
- [`hooks/devir_common.py`](hooks/devir_common.py) — ortak yardımcılar (git, not tarama/precedence, redaction, transcript token/dosya çıkarımı).
- [`hooks/devir_memory.py`](hooks/devir_memory.py) — `MEMORY.md` index'ine `flock` + atomik + idempotent upsert (paralel-session race koruması).

**Test:** [`hooks/devir_e2e_test.py`](hooks/devir_e2e_test.py) — geçici git repo + simüle harness payload'larıyla uçtan-uca regression (43/43).

```bash
python3 hooks/devir_e2e_test.py
```

## Tasarım gerekçesi

**Long-context degradation bir eğilimdir, "zayıf model" sorunu değil.** Model ne kadar güçlü
olursa olsun, bir session ~250–300k aralığına girdikçe context verimi düşme eğilimindedir —
long-context değerlendirmelerinde yaygın gözlenen bir örüntü. Daha büyük bir context penceresi
(ör. Fable'ın 1M token'ı) bunu *erteler*, ortadan kaldırmaz. devir, Claude Code + Opus gibi
araçlar için duvarın **önüne geçer** — erken (yaklaşık ~260k'da) flush eder ve kaçınılmaz sınırı,
lossy auto-compaction yerine kontrollü, yüksek-fidelity bir devir-teslime çevirir.

**Tasarım gereği human-in-the-loop.** Tek güçlü bir komut kompleks işi uçtan uca bitirebilir —
ama orta-akışta müdahale etmek zordur, özellikle çalışmanın ne kadar dökümantasyon veya işlem
ayrıntısı yüzeye çıkardığında söz sahibi olmak istediğinde. devir bunun yerine doğal
checkpoint'ler sunar: commit/push öncesi onay, resume'da belirsizlikte SOR, devam öncesi
staleness kontrolü ve her adımda incelenebilir artefakt (handoff notu, supervisor verdict) —
böylece araçla güreşmeden döngüde kalırsın. (Bu checkpoint'ler yapısaldır; farklı iş akışlarında
sonucu *ölçülebilir* biçimde iyileştirip iyileştirmediği henüz açık bir soru.)

Anthropic Fable ile tam, kanıta dayalı karşılaştırma — neyin **iddia edilmediğinin** (henüz eval
yok, maliyet/latency ölçülmedi) dürüst dökümü dahil — için:
[`docs/fable-comparison.md`](docs/fable-comparison.md).

## Kurulum

Bu repo bir **snapshot**'tır; tek kaynak (source of truth) çalışan kurulumdur: `~/.claude/`.

1. `skills/` → `~/.claude/skills/` altına kopyalayın.
2. `hooks/*.py` → `~/.claude/hooks/` altına kopyalayın.
3. [`settings.example.json`](settings.example.json)'daki `hooks` bloğunu `~/.claude/settings.json` ile birleştirin.
4. **L2 not gizliliği (opt-in commit):** global gitignore'a (`~/.config/git/ignore`) `**/.claude/docs/devir-notes/` ekleyin → notlar tüm projelerde **varsayılan lokal** kalır; commit gerekirse (cross-machine/takım) `git add -f`.
5. Doğrulama: `python3 ~/.claude/hooks/devir_e2e_test.py`

> Sync notu: değişiklikler `~/.claude`'da yapılır, sonra bu repoya kopyalanıp commit'lenir.
> (İleride symlink veya bir sync script'i ile tek-yönlü tutulabilir.)

## Dokümantasyon

- [`docs/workflow.md`](docs/workflow.md) — sistemin tam workflow'u: kullanıcı neyi/ne zaman tetikler, arka planda ne/ne zaman/neden çalışır (diyagramlarla).
- [`docs/fable-comparison.md`](docs/fable-comparison.md) — bu orchestration yaklaşımının Anthropic Fable ile dürüst, kanıta dayalı karşılaştırması.
- [`docs/diagrams/`](docs/diagrams/) — standalone SVG şemalar + **diyagram-güncelleme disiplini** ([`docs/diagrams/README.md`](docs/diagrams/README.md)). Skill/hook değiştiğinde diyagramlar da güncellenir; [`tools/check_doc_sync.py`](tools/check_doc_sync.py) sabit-, hook-wiring- ve skill-adı drift'ini yakalar.

## Lisans

[MIT](LICENSE) © 2026 İbrahim Sümbül.
