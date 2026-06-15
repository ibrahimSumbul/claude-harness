export const meta = {
  name: 'adversarial-review',
  description: 'Değişen kodu çok-eksenli bul → her bulguyu bağımsız Opus şüphecilerle ÇÜRÜTMEYE çalış → çoğunluk çürütemezse ayakta tut → yeni bulgu bitene kadar (loop-until-dry) tekrarla. Model-per-role: bulucular Sonnet, şüpheciler Opus (agent dosyalarının frontmatter\'ından).',
  phases: [
    { title: 'Scope', detail: 'değişen dosyalar + diff digest' },
    { title: 'Find', detail: 'correctness / security / reuse bulucuları (Sonnet) — loop-until-dry' },
    { title: 'Verify', detail: 'her taze bulgu için N adversarial şüpheci (Opus)' },
    { title: 'Synthesize', detail: 'doğrulanan bulgulardan rapor (Opus)' },
  ],
}

// ── Şemalar (StructuredOutput ile zorlanır → parse gerekmez) ────────────────
const SCOPE = {
  type: 'object', required: ['changedFiles', 'diffDigest'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    diffDigest: { type: 'string', description: 'Değişikliğin özlü, satır-referanslı dökümü' },
    summary: { type: 'string' },
  },
}
const FINDINGS = {
  type: 'object', required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['file', 'line', 'severity', 'title', 'detail', 'confidence'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { enum: ['high', 'medium', 'low'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          confidence: { type: 'number' },
        },
      },
    },
  },
}
const VERDICT = {
  type: 'object', required: ['refuted', 'confidence', 'reasoning'],
  properties: {
    refuted: { type: 'boolean' },
    confidence: { type: 'number' },
    reasoning: { type: 'string' },
    severity_adjustment: { type: 'string' },
  },
}
const REPORT = {
  type: 'object', required: ['report'],
  properties: { report: { type: 'string' }, summary: { type: 'string' } },
}

// ── Ayar ────────────────────────────────────────────────────────────────────
const DIMENSIONS = [
  { key: 'correctness', agentType: 'reviewer-correctness' },
  { key: 'security', agentType: 'reviewer-security' },
  { key: 'reuse', agentType: 'reviewer-reuse' },
]
const target = (typeof args === 'string' && args.trim())
  ? args.trim()
  : (args && args.target) || 'mevcut branch ile main arasındaki diff (git diff main...HEAD)'

// Bütçeye göre ölçekle (budget.total yoksa cömert varsayılan).
const tight = budget.total && budget.remaining() < 150_000
const SKEPTICS = tight ? 1 : 3          // bulgu başına şüpheci sayısı
const MAX_ROUNDS = tight ? 2 : 4        // loop-until-dry üst sınırı (runaway guard)
const DRY_STREAK = 2                     // kaç ardışık boş tur sonrası dur

const key = (f) => `${(f.file || '').toLowerCase()}:${f.line}:${(f.title || '').toLowerCase().slice(0, 60)}`

// ── Faz 1: Scope ──────────────────────────────────────────────────────────
phase('Scope')
const scope = await agent(
  `Bir adversarial code-review başlatıyoruz. İncelenecek hedef: ${target}.
Git ile değişikliği tespit et: değişen dosyaların listesini çıkar ve değişikliğin özlü, **satır-referanslı** bir digest'ini hazırla
(her dosya için neyin değiştiği + en kritik hunk'lar). Bulgu ARAMA — sadece kapsamı netleştir.
\`git diff\`/\`git --no-pager log\` kullanabilirsin. Değişiklik yoksa changedFiles boş döndür.`,
  { schema: SCOPE, phase: 'Scope', label: 'scope' },
)

if (!scope || !scope.changedFiles || scope.changedFiles.length === 0) {
  log('Değişiklik bulunamadı — inceleyecek bir şey yok.')
  return { confirmed: [], rounds: 0, scope: scope || null, report: 'Değişiklik yok; review atlandı.' }
}
log(`Kapsam: ${scope.changedFiles.length} dosya. Bulucular başlıyor (${SKEPTICS} şüpheci/bulgu, ≤${MAX_ROUNDS} tur).`)

// ── Faz 2+3: loop-until-dry — bul → dedup → çürüt ──────────────────────────
const seen = new Set()
const confirmed = []
let dry = 0
let round = 0

while (dry < DRY_STREAK && round < MAX_ROUNDS) {
  round++
  if (budget.total && budget.remaining() < 40_000) { log('Bütçe düşük — tur döngüsü erken bitti.'); break }

  const seenList = [...seen].slice(-40).join(' | ') || '(henüz yok)'

  // BARRIER: bu turdaki tüm bulucuları topla (dedup tüm boyutlar arası yapılmalı).
  const batches = await parallel(DIMENSIONS.map((d) => () =>
    agent(
      `Tur ${round}. Aşağıdaki değişiklikte kendi eksenindeki bulguları ara.
KAPSAM (değişen dosyalar): ${scope.changedFiles.join(', ')}
DIFF DIGEST:
${scope.diffDigest}

Dosyaları \`Read\`/\`Grep\` ile aç, çağrı yerlerini doğrula — tahminle bulgu yazma.
ZATEN BULUNANLARI TEKRAR ETME (başlık özetleri): ${seenList}
Yeni, gerçek, tekrarlanabilir bulgular döndür; yoksa boş liste.`,
      { agentType: d.agentType, phase: 'Find', label: `find:${d.key}#${round}`, schema: FINDINGS },
    ).then((r) => ({ key: d.key, findings: (r && r.findings) || [] })),
  ))

  const fresh = []
  for (const b of batches.filter(Boolean)) {
    for (const f of b.findings) {
      const k = key(f)
      if (seen.has(k)) continue
      seen.add(k)
      fresh.push({ ...f, dimension: b.key })
    }
  }

  if (fresh.length === 0) { dry++; log(`Tur ${round}: taze bulgu yok (kuru tur ${dry}/${DRY_STREAK}).`); continue }
  dry = 0
  log(`Tur ${round}: ${fresh.length} taze bulgu → ${SKEPTICS} şüpheciyle çürütme denemesi.`)

  // Her taze bulguyu bağımsız şüpheciye(lere) ver; çoğunluk çürütürse düşür.
  const judged = await parallel(fresh.map((f) => () =>
    parallel(Array.from({ length: SKEPTICS }, (_, i) => () =>
      agent(
        `Şu review bulgusunu ÇÜRÜTMEYE çalış (şüpheci #${i + 1}). Belirsizsen refuted=true.
BULGU [${f.dimension}/${f.severity}] ${f.file}:${f.line}
${f.title}
${f.detail}`,
        { agentType: 'skeptic-verifier', phase: 'Verify', label: `verify:${f.dimension}:${f.file}:${f.line}#${i + 1}`, schema: VERDICT },
      ),
    )).then((votes) => {
      const v = votes.filter(Boolean)
      const refuted = v.filter((x) => x.refuted).length
      const survives = v.length > 0 && refuted < Math.ceil(v.length / 2) // çoğunluk çürütemedi
      return { finding: f, survives, votes: v, refutedCount: refuted }
    }),
  ))

  for (const j of judged.filter(Boolean)) {
    if (j.survives) confirmed.push({ ...j.finding, votes: j.votes })
  }
  log(`Tur ${round}: ${confirmed.length} doğrulanmış bulgu (toplam).`)
}

// ── Faz 4: Synthesize ───────────────────────────────────────────────────────
phase('Synthesize')
if (confirmed.length === 0) {
  log('Doğrulanmış bulgu yok — temiz.')
  return { confirmed: [], rounds: round, scope, report: '✅ Adversarial review: çoğunluk-doğrulamasından geçen bulgu yok.' }
}

const synth = await agent(
  `Bir adversarial code-review'ın doğrulanmış bulgularından senior bir rapor yaz (abartısız, eyleme dönük).
HEDEF: ${target}
DOĞRULANMIŞ BULGULAR (her biri çoğunluk şüpheciyi geçti):
${JSON.stringify(confirmed.map(({ votes, ...f }) => f), null, 2)}

severity'ye göre grupla (high önce). Her bulgu için: konum, sorun, önerilen düzeltme. Üstte 1-2 cümle özet.`,
  { schema: REPORT, model: 'opus', phase: 'Synthesize', label: 'synthesize' },
)

return {
  confirmed: confirmed.map(({ votes, ...f }) => f),
  rounds: round,
  scope: { changedFiles: scope.changedFiles, summary: scope.summary },
  report: (synth && synth.report) || '(rapor üretilemedi)',
}
