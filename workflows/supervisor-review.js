export const meta = {
  name: 'supervisor-review',
  description: 'Bir KONUYU (karar/plan/tasarım/doküman/strateji/kod-alanı — diff değil) tek eksende örtüşmeyen dilimlere böl → her dilimi bağımsız Opus\'larla paralel değerlendir (yüksek-stakes 2x) → iki Opus ayrışırsa KORU (ayrışma = sinyal, ortalanmaz) → tek karar artefaktına sentezle. adversarial-review\'in yargı tümleyeni: o anlaşmazlığı çökertir, bu korur. Tüm değerlendiriciler Opus.',
  phases: [
    { title: 'Frame', detail: 'decomposer (Opus): eksen seç + MECE dilimler + per-dilim derinlik' },
    { title: 'Evaluate', detail: 'her dilim için depth kadar bağımsız Opus değerlendirici (paralel)' },
    { title: 'Reconcile', detail: '2x dilimlerde ayrışmayı deterministik yakala (kod, ajan değil)' },
    { title: 'Synthesize', detail: 'inline Opus: dilim yargılarını + ayrışmaları tek karara birleştir' },
  ],
}

// ── Şemalar (StructuredOutput ile zorlanır → parse gerekmez) ────────────────
const DECOMPOSITION = {
  type: 'object', required: ['axis', 'axisRationale', 'slices'],
  properties: {
    axis: { enum: ['temporal', 'technical', 'concern'] },
    axisRationale: { type: 'string' },
    slices: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'scope', 'outOfScope', 'keyQuestions', 'depth', 'stakes', 'uncertainty'],
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          scope: { type: 'string' },
          outOfScope: { type: 'string' },
          keyQuestions: { type: 'array', items: { type: 'string' } },
          depth: { type: 'integer', enum: [1, 2] },
          depthReason: { type: 'string' },
          stakes: { enum: ['low', 'med', 'high'] },
          uncertainty: { enum: ['low', 'med', 'high'] },
        },
      },
    },
    coverageGaps: { type: 'array', items: { type: 'string' } },
    overlapRisks: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const ASSESSMENT = {
  type: 'object', required: ['sliceId', 'verdict', 'confidence', 'questionAnswers'],
  properties: {
    sliceId: { type: 'string' },
    verdict: { enum: ['strong', 'adequate', 'weak', 'blocked'] },
    confidence: { type: 'number' },
    questionAnswers: {
      type: 'array',
      items: {
        type: 'object',
        required: ['question', 'answer', 'certain'],
        properties: {
          question: { type: 'string' },
          answer: { type: 'string' },
          evidence: { type: 'string' },
          certain: { type: 'boolean' },
        },
      },
    },
    keyRisks: {
      type: 'array',
      items: { type: 'object', properties: { title: { type: 'string' }, severity: { enum: ['high', 'medium', 'low'] }, detail: { type: 'string' } } },
    },
    openQuestions: { type: 'array', items: { type: 'string' } },
    recommendation: { type: 'string' },
  },
}
const VERDICT = {
  type: 'object', required: ['report', 'overall'],
  properties: {
    report: { type: 'string' },
    overall: { enum: ['go', 'go-with-conditions', 'no-go', 'needs-more-info'] },
    sliceRollup: {
      type: 'array',
      items: { type: 'object', properties: { sliceId: { type: 'string' }, verdict: { type: 'string' }, depth: { type: 'integer' }, diverged: { type: 'boolean' }, unverified: { type: 'boolean' } } },
    },
    divergences: {
      type: 'array',
      items: { type: 'object', properties: { sliceId: { type: 'string' }, positionA: { type: 'string' }, positionB: { type: 'string' }, crux: { type: 'string' }, lean: { type: 'string' } } },
    },
    coverageGaps: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}

// ── Ayar ────────────────────────────────────────────────────────────────────
const subject = (typeof args === 'string' && args.trim())
  ? args.trim()
  : (args && (args.subject || args.target)) || null
const axisArg = (args && args.axis) || 'auto'           // temporal | technical | auto
const depthArg = (args && args.depth) || null            // all1x | all2x | null
// Bütçeye göre ölçekle (çok-Opus skeptic'ten ağır → daha yüksek eşik).
const tight = budget.total && budget.remaining() < 200_000
const MAX_SLICES = tight ? 3 : ((args && Number(args.maxSlices)) || 5)

if (!subject) {
  log('Konu (subject) verilmedi — değerlendirilecek bir şey yok. Skill args ile konuyu geçmeli.')
  return { overall: 'needs-more-info', report: 'Konu verilmedi; supervisor-review atlandı. args ile karar/plan/tasarım/yol geç.', slices: [] }
}

// ── Faz 1: Frame (decomposer, Opus) ─────────────────────────────────────────
phase('Frame')
const decomp = await agent(
  `Bir supervisor-review için konuyu yargı-değerlendirmesine HAZIRLA (değerlendirme YAPMA).
KONU: ${subject}
İSTENEN EKSEN: ${axisArg} (auto ise sen seç; temporal=geçmiş/şimdi/gelecek, technical=bileşen, concern=doğruluk/fizibilite/risk/alternatifler).
Konu bir yol/PR ise materyali Read/Grep/Bash(git) ile aç. ${MAX_SLICES} dilimi geçme.
Örtüşmeyen (MECE) 2-${MAX_SLICES} dilim üret. Sayıyı önce SEÇİLEN EKSENİN doğal MECE dikişlerinden çıkar (temporal ~3); takdiri-granül eksenlerde (technical/concern) karmaşıklığa kalibre et (tek-boyutlu→2, çok-yönlü→3-4, karmaşık yüksek-stakes→${MAX_SLICES}'a kadar). ${MAX_SLICES}'a ŞİŞİRME (overlapRisk); karmaşığı az-dilimleme yapma (coverageGap). Her dilime kapsam/kapsam-dışı/net sorular/derinlik(1|2)/stakes/uncertainty ata; coverageGaps + overlapRisks self-rapor et.`,
  { agentType: 'decomposer', phase: 'Frame', label: 'frame', schema: DECOMPOSITION },
)

if (!decomp || !Array.isArray(decomp.slices) || decomp.slices.length === 0) {
  log('Decomposer dilim üretemedi — review atlandı.')
  return { overall: 'needs-more-info', report: 'Konu dilimlenemedi; decomposer boş döndü.', decomposition: decomp || null, slices: [] }
}

// Dilimleri MAX_SLICES'a kırp (en düşük stakes'i düşür) + <2 uyarısı.
const stakeRank = { high: 3, med: 2, low: 1 }
let slices = decomp.slices.slice()
if (slices.length > MAX_SLICES) {
  const sorted = slices.slice().sort((a, b) => (stakeRank[b.stakes] || 1) - (stakeRank[a.stakes] || 1))
  const kept = new Set(sorted.slice(0, MAX_SLICES).map((s) => s.id))
  const dropped = slices.filter((s) => !kept.has(s.id)).map((s) => s.id)
  slices = slices.filter((s) => kept.has(s.id))
  log(`⚠ Dilim sayısı ${MAX_SLICES}'a kırpıldı (bütçe/sınır) — düşürülen (düşük-stakes): ${dropped.join(', ')}.`)
}
if (slices.length < 2) log(`⚠ Yalnız ${slices.length} dilim — gerçek bir decomposition değil; konu tek-boyutlu olabilir.`)
log(`Eksen: ${decomp.axis} (${decomp.axisRationale || ''}). ${slices.length} dilim.`)
if ((decomp.coverageGaps || []).length) log(`⚠ Decomposer kapsama-boşluğu bildirdi: ${decomp.coverageGaps.join(' | ')}`)
if ((decomp.overlapRisks || []).length) log(`⚠ Decomposer örtüşme-riski bildirdi: ${decomp.overlapRisks.join(' | ')}`)

// Per-dilim derinlik planı (deterministik): decomposer-kararı → user override → bütçe-clamp.
let depths = slices.map((s) => (Number(s.depth) === 2 ? 2 : 1))
if (depthArg === 'all1x') depths = slices.map(() => 1)
else if (depthArg === 'all2x') depths = slices.map(() => 2)
else if (tight) {
  // Dar bütçe: hepsini 1x'e indir, ama 2x planlanan EN yüksek-stakes tek dilimi koru (karar-sürücüsü).
  let topIdx = -1, topRank = -1
  slices.forEach((s, i) => { const r = stakeRank[s.stakes] || 1; if (depths[i] === 2 && r > topRank) { topRank = r; topIdx = i } })
  depths = depths.map((d, i) => (i === topIdx ? 2 : 1))
  log(`Bütçe dar — derinlikler 1x'e indirildi${topIdx >= 0 ? `, yalnız en yüksek-stakes dilim (${slices[topIdx].id}) 2x korundu` : ''} (ayrışma-tespiti bu turda kısıtlı).`)
}

// ── Faz 2: Evaluate (slice-evaluator, Opus ×depth, paralel-of-paralel) ──────
phase('Evaluate')
log(`Değerlendirme başlıyor: ${slices.map((s, i) => `${s.id}=${depths[i]}x`).join(' · ')}.`)
const sliceRuns = await parallel(slices.map((s, i) => () => {
  let d = depths[i]
  // In-loop bütçe tabanı (adversarial-review'den): fan-out öncesi düşükse 1x'e in.
  if (budget.total && budget.remaining() < 40_000 && d > 1) {
    d = 1
    log(`Bütçe düşük — dilim ${s.id} 1x'e indirildi.`)
  }
  const qs = (s.keyQuestions || []).map((q, k) => `  ${k + 1}. ${q}`).join('\n')
  return parallel(Array.from({ length: d }, (_, run) => () =>
    agent(
      `Bir konunun TEK dilimini yargı için değerlendir (bağımsız değerlendirici #${run + 1}).
KONU: ${subject}
EKSEN: ${decomp.axis}
DİLİM [${s.id}] ${s.title}
KAPSAM: ${s.scope}
KAPSAM-DIŞI (girme): ${s.outOfScope}
YANITLA (yalnız bunlar):
${qs}
Önce ilgili materyali oku (yol/PR ise Read/Grep/Bash(git)). Her soruyu certain bayrağıyla yanıtla; yanıtlayamadığını openQuestions'a koy (uydurma). Riskleri + dilim yargısını (strong/adequate/weak/blocked) + öneriyi döndür. Bu YARGI değerlendirmesidir, satır-bazlı bug avı DEĞİL.`,
      { agentType: 'slice-evaluator', phase: 'Evaluate', label: `eval:${s.id}#${run + 1}`, schema: ASSESSMENT },
    ),
  )).then((runs) => ({ slice: s, depth: d, plannedDepth: depths[i], runs: (runs || []).filter(Boolean) }))
}))

// ── Faz 3: Reconcile (deterministik — ajan değil, kod) ──────────────────────
phase('Reconcile')
const num = (x, dflt) => (typeof x === 'number' ? x : dflt)
function diverged(a, b) {
  if (!a || !b) return false
  if (a.verdict !== b.verdict) return true
  if (Math.abs(num(a.confidence, 0.5) - num(b.confidence, 0.5)) > 0.4) return true
  // Aynı soruda İKİSİ de certain ama yanıtlar çelişiyorsa → ayrışma.
  const am = {}
  for (const q of a.questionAnswers || []) {
    if (q && q.certain) am[(q.question || '').trim().toLowerCase()] = (q.answer || '').trim().toLowerCase()
  }
  for (const q of b.questionAnswers || []) {
    if (!q || !q.certain) continue
    const k = (q.question || '').trim().toLowerCase()
    if (am[k] !== undefined && am[k] !== (q.answer || '').trim().toLowerCase()) return true
  }
  return false
  // NOT: "disjoint risk setleri" kuralı kasıtlı ELENDİ — risk başlıkları sözcük-bazlı
  // farklılaştığından neredeyse her zaman ayrık görünür → yanlış-ayrışma üretirdi.
}

const consolidated = []
const divergences = []
let blockedCount = 0
let unverifiedCount = 0
for (const sr of sliceRuns.filter(Boolean)) {
  const s = sr.slice
  const runs = sr.runs || []
  if (runs.length === 0) {
    // Tüm değerlendiriciler hata verdi (transient) → SESSİZCE temiz sayma.
    blockedCount++
    consolidated.push({ sliceId: s.id, title: s.title, depth: sr.depth, verdict: 'blocked', diverged: false, unverified: true, assessments: [], note: 'tüm değerlendiriciler hata verdi (transient)' })
    log(`⚠ Dilim ${s.id}: tüm değerlendiriciler hata verdi → blocked/unverified (sessiz temiz DEĞİL).`)
    continue
  }
  if (runs.length === 1) {
    const a = runs[0]
    const shouldHave2x = (a.openQuestions || []).length >= 3
    // 2x PLANLANDI ama tek değerlendirme tamamlandı (bütçe-clamp VEYA transient hata) →
    // ikili-doğrulama eksik. sr.depth çalışma-anında düşmüş olabilir; planlanan derinliğe bak.
    const unver = sr.plannedDepth > 1
    if (unver) { unverifiedCount++; log(`⚠ Dilim ${s.id}: 2x planlandı ama tek değerlendirme tamamlandı (bütçe ya da hata) → unverified (tam ağırlıkta sayılmayacak).`) }
    if (shouldHave2x) log(`↑ Dilim ${s.id}: 1x ama ${a.openQuestions.length} açık soru → 2x olmalıydı (synth'e işaretlendi).`)
    consolidated.push({ sliceId: s.id, title: s.title, depth: sr.depth, verdict: a.verdict, confidence: num(a.confidence, null), diverged: false, unverified: unver, shouldHave2x, assessments: [a] })
    continue
  }
  // depth>=2, en az 2 koşum: ilk ikiyi kıyasla.
  const [a, b] = runs
  const div = diverged(a, b)
  if (div) {
    divergences.push({ sliceId: s.id, verdictA: a.verdict, verdictB: b.verdict, confidenceA: num(a.confidence, null), confidenceB: num(b.confidence, null) })
    log(`⊿ Dilim ${s.id}: iki bağımsız Opus AYRIŞTI (${a.verdict} vs ${b.verdict}) — ayrışma korunuyor, ortalanmıyor.`)
  } else {
    log(`✓ Dilim ${s.id}: iki bağımsız Opus HEMFİKİR (${a.verdict}) — güçlü güven sinyali.`)
  }
  consolidated.push({
    sliceId: s.id, title: s.title, depth: sr.depth,
    verdict: div ? `${a.verdict}/${b.verdict}` : a.verdict,
    confidence: Math.min(num(a.confidence, 0.5), num(b.confidence, 0.5)),
    diverged: div, agreement: !div, unverified: false, assessments: [a, b],
  })
}

// ── Faz 4: Synthesize (inline Opus — agentType yok, adversarial-review gibi) ─
phase('Synthesize')
// Synth prompt'unu hafif tut: ağır iç-veriyi kıs.
const slim = consolidated.map((c) => ({
  sliceId: c.sliceId, title: c.title, depth: c.depth, verdict: c.verdict,
  confidence: c.confidence, diverged: c.diverged, unverified: c.unverified, shouldHave2x: !!c.shouldHave2x,
  assessments: (c.assessments || []).map((a) => ({
    verdict: a.verdict, confidence: a.confidence, recommendation: a.recommendation,
    keyRisks: (a.keyRisks || []).slice(0, 6),
    openQuestions: (a.openQuestions || []).slice(0, 6),
    answers: (a.questionAnswers || []).map((q) => ({ q: q.question, a: q.answer, certain: q.certain })),
  })),
}))

const synth = await agent(
  `Bir supervisor-review'ın dilim yargılarından senior, eyleme-dönük tek bir KARAR ARTEFAKTI yaz (abartısız).
KONU: ${subject}
EKSEN: ${decomp.axis} — ${decomp.axisRationale || ''}
DECOMPOSER KAPSAMA-BOŞLUKLARI: ${JSON.stringify(decomp.coverageGaps || [])}
AYRIŞAN DİLİMLER (iki Opus bölündü): ${JSON.stringify(divergences)}
DİLİM SONUÇLARI (consolidated):
${JSON.stringify(slim, null, 2)}

Kurallar:
1. Ayrışan dilimlerde ORTALAMA ALMA — iki yargıyı tek bir orta-değere İNDİRME. Bunun yerine her ayrışan dilimi açıkça yüzeye çıkar: iki okumayı da ver, ayrılığın KRUX'unu adlandır, gerekçeli bir LEAN (eğilim) söyle.
2. ZAYIF-HALKA tartımı (ortalama değil): yüksek-stakes dilimleri daha ağır say; tek bir yüksek-stakes düşük-confidence/ayrışan dilim geneli 'go-with-conditions' veya 'needs-more-info'ya çekebilir.
3. coverageGaps + her blocked/unverified dilimi kararın içine KATMA olarak işle (görünüşte temiz bir rapor bile bir dilim bloke olduğu için 'needs-more-info' olabilir).
4. unverified (transient-hata) dilimleri AYRI bir bölümde, tam ağırlıkta DEĞİL.
5. Tek, altitüde-uygun bir değerlendirme yaz (düz yargı prozası + dilim-bazlı rollup + genel öneri) — bir bug listesi DEĞİL.
overall ∈ {go, go-with-conditions, no-go, needs-more-info}. Bu advisory bir artefakt — otomatik aksiyon yok, insan döngüde.`,
  { schema: VERDICT, model: 'opus', phase: 'Synthesize', label: 'synthesize' },
)

return {
  overall: (synth && synth.overall) || 'needs-more-info',
  report: (synth && synth.report) || '(rapor üretilemedi)',
  axis: decomp.axis,
  slices: slim.map((c) => ({ sliceId: c.sliceId, title: c.title, depth: c.depth, verdict: c.verdict, diverged: c.diverged, unverified: c.unverified })),
  divergences,
  coverageGaps: decomp.coverageGaps || [],
  blockedCount,
  unverifiedCount,
}
