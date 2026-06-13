# claude-harness

**Claude Code için session devir-teslim (context-flush) sistemi.** Uzun-context
degradasyonu (~300k token) başlamadan önce çalışan session'ın state'ini yüksek-fidelity
kalıcı katmanlara yazar, temiz bir session'a geçmeyi ve oradan **güvenli devam**ı sağlar.

> `devir` (TR): bir işin/görevin başkasına veya bir sonrakine teslim edilmesi.

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
| **L2** | Git-tracked unique-ID not | `<repo>/.claude/docs/devir-notes/<id>.md` | Durable, cross-machine, takım-paylaşımlı |
| **L3** | Hook güvenlik ağı | `~/.claude/hooks/devir-*.py` | Model işbirliği gerekmeden mekanik yakalama/restore (advisory) |

L1 + L2'yi **model** (skill) yazar; L3 **deterministik** çalışır (model uymasa bile).

## Bileşenler

**Skills** (`disable-model-invocation: true` — yalnızca kullanıcı tetikler):
- [`skills/devir/SKILL.md`](skills/devir/SKILL.md) — manuel `/devir`: canlı git state yakala → L1+L2 yaz → handoff bloğu → commit kapanışı (Faz 0-8). Mimari gerekçeler: [`skills/devir/DESIGN.md`](skills/devir/DESIGN.md).
- [`skills/devir-resume/SKILL.md`](skills/devir-resume/SKILL.md) — `/devir-resume`: yeni session'da not seç → staleness (git-drift) kontrolü → ne anladığını söyle → **onay al** → devam.

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

## Kurulum

Bu repo bir **snapshot**'tır; tek kaynak (source of truth) çalışan kurulumdur: `~/.claude/`.

1. `skills/` → `~/.claude/skills/` altına kopyalayın.
2. `hooks/*.py` → `~/.claude/hooks/` altına kopyalayın.
3. [`settings.example.json`](settings.example.json)'daki `hooks` bloğunu `~/.claude/settings.json` ile birleştirin.
4. Doğrulama: `python3 ~/.claude/hooks/devir_e2e_test.py`

> Sync notu: değişiklikler `~/.claude`'da yapılır, sonra bu repoya kopyalanıp commit'lenir.
> (İleride symlink veya bir sync script'i ile tek-yönlü tutulabilir.)

## Dokümantasyon

- [`docs/workflow.md`](docs/workflow.md) — sistemin tam workflow'u: kullanıcı neyi/ne zaman tetikler, arka planda ne/ne zaman/neden çalışır (diyagramlarla).
- [`docs/fable-comparison.md`](docs/fable-comparison.md) — bu orchestration yaklaşımının Anthropic Fable ile dürüst, kanıta dayalı karşılaştırması.
- [`docs/diagrams/`](docs/diagrams/) — standalone SVG şemalar + **diyagram-güncelleme disiplini** ([`docs/diagrams/README.md`](docs/diagrams/README.md)). Skill/hook değiştiğinde diyagramlar da güncellenir; [`tools/check_doc_sync.py`](tools/check_doc_sync.py) sabit-drift'i yakalar.
