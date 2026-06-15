---
name: devir-land
description: Bitmiş, kendi içinde kapalı küçük bir iş dilimini (döküman + plan + ilgili PR/branch koduna ait kod) context sınırına ÇARPMADAN, AYNI session'da kalarak commit + push ile İNDİR (land). /devir'in tümleyeni — yarım iş için DEĞİL, BİTMİŞ dilim için. Handoff notu YAZMAZ, L1 memory'ye DOKUNMAZ, fresh session AÇMAZ (süreklilik YOK). Saf entegrasyon — cerrahi pathspec (asla -A/-u), fetch + rebase-before-push, force-push YOK. Çakışma/divergence olursa kör çözme YOK → mekanik bağlamı topla → Opus supervisor subagent'a incelet → SADECE SIMPLE & güvenli ise uygula+devam+raporla, aksi halde kullanıcı onayına çıkar (foreign-file HER ZAMAN escalate). Kullanıcı "land et", "tamamlanan dilimi indir", "bitti commit+push", "ilgili PR'a indir" derse. Mimari — ../devir/DESIGN.md (§4 paralel-conflict + §7 devir-land).
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh:*), Bash(pnpm:*), Bash(python3:*), Bash(date:*), Read, Edit, Grep, Task
---

# /devir-land — Bitmiş dilimi indir (commit + push)

Küçük, **kapalı**, **BİTMİŞ** bir iş dilimini context sınırına gelmeden **AYNI session'da** land et: dökümanlar + planlar + **ilgili PR/branch'e ait bitmiş kod** → cerrahi commit + güvenli push. `/devir`'in tümleyeni: o yarım işi (~260k sınırı) handoff notu + fresh session'a devreder; **`/devir-land` ise erken biten dilimi entegre eder** — not YOK, fresh session YOK, süreklilik YOK. Yarım iş → `/devir` kullan.
**Mimari, paralel-conflict, single-writer, conflict felsefesi → [`../devir/DESIGN.md`](../devir/DESIGN.md) (§4 + §7).** Bu dosya operasyonel adımlar.

## İlkeler (önce oku)
- **Sadece BİTMİŞ dilim için.** Yarım/half-edited iş, kırmızı test, açık `[TODO]` → land YOK; `/devir` (yarım iş notu) öner. DONE GATE (Faz 1) geçmiyorsa **DUR**.
- **Saf commit+push — NOT/MEMORY'ye DOKUNMA.** `session-state` yazma, `devir_memory.py upsert` YAPMA, L2 devir notu üretme/consume/flip etme. Süreklilik YOK. (Branch'in açık notu varsa ve dilim onu açıkça bitiriyorsa → kullanıcıya yalnızca **belirt**: "`/devir-resume` ile consume edebilir veya notu elle `consumed` yapabilirsin." `/devir-land` nota ASLA dokunmaz.)
- **State'i komut çıktısından oku, recall'dan DEĞİL** (canlı git). Emin değilsen **"(belirsiz)"** yaz, UYDURMA.
- **Cerrahi & non-destructive ol — paralel & skalar session'lara ZARAR VERME.** paralel = diğer eşzamanlı worktree/branch session'ları; skalar = bu tek lineer session zaman çizgisi. Garanti: cerrahi pathspec · additive (asla destructive) · **force-push YOK** · **`git add -A`/`-u` YOK** · rebase SADECE local-unpushed commit'lere · yabancı hunk **asla** atılmaz.
- **Çakışmada körü körüne ne çöz ne sor:** önce mekanik bağlam → **Opus supervisor subagent** → verdict gate (Faz 5). Belirsizlik veya foreign-territory = **DUR ve SOR**.

## Faz 0 — Hazırlık (repo + branch + hedef PR + branch güvenliği)
- Repo + branch (komut çıktısından, recall'dan değil):
  - `git rev-parse --show-toplevel` (repo değilse → **DUR**: "land git repo gerektirir")
  - `git branch --show-current` (detached HEAD ise → **DUR**, branch öner)
  - slug = küçük harf, `[^a-z0-9._-]`→`-` (commit mesajı konusu için).
- **İlgili PR/branch'i tespit et** (hedef = "ilgili pr veya branch"):
  - `git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "upstream yok"`
  - `gh pr list --head "$(git branch --show-current)" --state open 2>/dev/null | grep . || echo "bu branch için açık PR yok/bilinmiyor"` (gh unauth ise PR durumu **UYDURMA**, "bilinmiyor" de).
  - Mevcut branch'in upstream'i ve/veya açık PR'ı varsa → hedef = bu. Aksi halde branch hedefiyle devam.
- **Branch güvenliği (ZORUNLU):** hedef `main`/`master`/protected ise → **doğrudan commit ETME**. Dilimin slug'ıyla `feat/<slug>` (veya mevcut PR branch'i) öner, kullanıcıdan onay al → onaydan SONRA `git switch -c feat/<slug>`. Protected'a yazmayı asla sessizce yapma.

## Faz 1 — Canlı state + DONE GATE (land etmeden ÖNCE — /devir promotion-gate analoğu)
Dilim gerçekten **BİTTİ Mİ**? Önce mekanik kanıtla — recall'a güvenme.
- Canlı working tree: `git status --short` · son commitler: `git --no-pager log --oneline -5`.
- DONE GATE (hepsi ✓ olmalı; biri bile değilse → **DUR**, `/devir` öner):
  - Dilime ait dosyalarda **yarım/half-edited yok** (status'ta beklenmedik `M` yok).
  - Dilim dosyalarında bekleyen `[TODO]` / `FIXME(devir)` / boş stub yok — house-marker taraması (`grep -E`, exit-kodu birebir): `grep -nE '\[TODO\]|FIXME\(devir\)' -- <dilim dosyaları>`. Eşleşme (exit 0) → marker bekliyor, DONE GATE GEÇMEZ → **DUR**, `/devir` öner. Eşleşme yok (exit 1) → kapı geçer. grep hatası (exit ≥2, ör. yol yok) → **"(belirsiz)"**, **DUR** — temiz sanma. (Bare `TODO`/`FIXME` taranmaz: `[TODO]`/`FIXME(devir)` ailenin kasıtlı işareti; düz yorumları bloklamayız.) Marker taraması zorunlu olarak eksiktir → asıl bitmişlik sinyali Faz 1'in verbatim test+tsc kapısıdır.
  - **Kod değiştiyse** test + typecheck **verbatim** geçer — çıktıyı **verbatim** göster:
    ```bash
    pnpm test:run
    pnpm exec tsc --noEmit
    ```
    Kırmızı varsa → land YOK.
  - Dilim **kendi içinde kapalı**: tek mantıksal birim, başka WIP'e bağımlı değil.
- Kapı geçmiyorsa net söyle: *"Bu dilim henüz bitmemiş görünüyor (<sebep>). `/devir-land` sadece bitmiş dilim içindir; yarım iş için `/devir` kullan."*

## Faz 2 — Cerrahi staging (kapsam ayrımı + onay #1)
Amaç: **SADECE** bu dilimin dosyalarını (döküman + plan + ilgili koda ait kod) seç; alakasız WIP'i dışarıda tut.
- Kaynak liste: `git status --porcelain` · `git --no-pager diff --stat` · `git --no-pager diff --stat --staged` (kullanıcı önceden stage'lemiş olabilir).
- **ÖNCEDEN-staged kümeyi yakala (pathspec çıkarmadan ÖNCE):**
  ```bash
  git --no-pager diff --cached --name-only   # ÖNCEDEN staged küme — dilime ait olmayan dosya var mı?
  ```
  Bu kümede dilim pathspec'i **DIŞINDA** dosya varsa = yabancı/önceden-stage'lenmiş WIP (muhtemelen paralel session). Bunu commit'e **SIZDIRMA**: kullanıcıya göster, onayıyla **SADECE** o yolları cerrahi unstage et — `git restore --staged -- <yabancı yollar>` (asla `git reset` ile tüm index; working-tree değişikliği **KORUNUR/silinmez**) — ya da **DUR**. `git add -- <slice>` zaten-staged yabancı dosyayı **KALDIRMAZ**; bu yüzden açıkça temizlenmeli.
- Çıktıdan dilim dosyalarını **kullanıcıyla teyit ederek** somut bir **pathspec listesi** çıkar (ör. `docs/plan-x.md skills/foo/SKILL.md src/foo/handler.ts`).
- Stage'le **yalnızca açık pathspec ile** (`--` ayıracı zorunlu — dosya adı flag/branch sanılmasın):
  ```bash
  git add -- docs/plan-x.md skills/foo/SKILL.md src/foo/handler.ts
  ```
  - **Bir dosyanın yalnız bir kısmı dilime aitse:** `git add -p` KULLANMA — interaktif (stdin y/n/s/e döngüsü), bu non-interaktif agent ortamında desteklenmez (bkz. `git add -i`/`git rebase -i` yasağı, NEVER listesi) → hang/error. İki yol:
    1. **Tercih edilen:** Dosya pathspec ile temiz ayrılamıyorsa dilim **kendi içinde kapalı DEĞİLDİR** (Faz 1 DONE GATE'i ihlal) → sessizce hunk-bölme **YAPMA**, **DUR ve kullanıcıya bildir** (dilimi ayırması veya `/devir` kullanması için).
    2. Gerçekten gerekiyorsa non-interaktif patch ile: `git --no-pager diff -- <dosya> > /tmp/devir-slice.patch` → patch'i `Edit` ile yalnız dilim hunk'larına indir → `git apply --cached /tmp/devir-slice.patch` (yine açık pathspec, `-A`/`-u` YOK). Stage sonrası aşağıdaki doğrulamayı çalıştır.
- Stage sonrası **fail-closed doğrula** — staged küme **TAM OLARAK** teyitli pathspec olmalı:
  ```bash
  git --no-pager diff --cached --name-only   # staged küme TAM OLARAK dilim pathspec'i mi? (eşit değilse fazlalıkları çıkar)
  git status --short                          # dilim DIŞI değişiklikler unstaged kalmalı (sakla, stage ETME)
  ```
  **staged küme == teyitli pathspec değilse** → fazla yolları `git restore --staged -- <fazla yollar>` ile **cerrahi çıkar** (yine `-A`/`-u`/whole-index reset YOK; working-tree korunur) → **yeniden doğrula**. Eşitlik sağlanana kadar Onay #1'e/commit'e **geçme**.
- **`-A`/`-u` YASAK:** `git add -A` / `git add -u`, çalışma ağacındaki **tüm** (veya tüm tracked) değişikliği kör stage'ler → başka paralel session'ın aynı worktree'de bıraktığı WIP'i, yarım dosyaları, alakasız değişikliği commit'e sızdırır (hem skalar timeline'ı kirletir hem paralel session'ın yarım işini başka commit'e gömer). Kapsam **her zaman explicit + teyitli**.
- **Onay #1 (commit öncesi):** kullanıcıya staged kapsamı göster, **onay al** (otomatik commit yok).

## Faz 3 — Commit kapanışı (trailer'sız, onay zorunlu)
- Commit yalnız Faz 2'de stage'lenen dilimi kapsar:
  ```bash
  git commit -m "<type>(<scope>): <dilim özeti>"
  ```
- **AI co-author trailer YOK** (kullanıcı tercihi; repo konvansiyonu trailer ZORUNLU kılıyorsa ona uy).
- Commit sonrası: `git status --short` ile dilim-dışı WIP'in hâlâ unstaged/dokunulmamış olduğunu doğrula.

## Faz 4 — Conservative push (fetch + rebase-before-push, force YOK, retry-once)
- **Onay #2 (push öncesi):** kullanıcıya commit'i + push hedefini (remote/branch) göster, **onay al**.
- Remote'u canlı çıktıdan türet (sabit `origin` varsayma) ve **boş-remote'u gerçek kontrol-akışı guard'ıyla yakala** (yorum değil):
  ```bash
  REMOTE=$(git remote | grep -qx origin && echo origin || git remote | head -1)
  BR=$(git branch --show-current)
  if [ -z "$REMOTE" ]; then
    # remote YOK → push edilemez: yalnız local commit kalır; Faz 6'da "remote yok, push edilmedi" olarak raporla. fetch/rebase/push ATLA.
    echo "remote yok → yalnız local commit; push edilmedi"
  else
    git fetch "$REMOTE" "$BR"
    # ... aşağıdaki divergence tespiti + rebase + push adımları SADECE remote varken çalışır ...
  fi
  ```
  > Guard'ın amacı: `REMOTE` boşken aşağıdaki `git push "" "$BR"` çağrısının `fatal: bad repository ''` ile kafa karıştırıcı bir hata vermesini engellemek; bunun yerine temiz "push edilmedi" raporuna (Faz 6) ulaşmak. Tüm fetch/divergence/rebase/push dizisi `[ -n "$REMOTE" ]` koşuluna bağlıdır.
- Divergence/non-fast-forward'ı push DENEMEDEN önce **mekanik** tespit et — `@{u}` DEĞİL, az önce fetch'lenen remote-tracking ref `$REMOTE/$BR` ile (Faz 5 ile aynı kural; `@{u}` upstream-tracking yapılandırılmamışsa — PR var ama `--set-upstream` hiç çalışmamışsa — `fatal` verir):
  ```bash
  git rev-parse --verify -q "$REMOTE/$BR" >/dev/null 2>&1 || echo "remote-tracking ref yok → ilk push: rebase'e gerek yok"
  git --no-pager log --oneline "$REMOTE/$BR"..@ 2>/dev/null   # benim önde (push edilecek) = rebase edilebilir pencere
  git rev-list --count "@..$REMOTE/$BR" 2>/dev/null           # remote'un benden önde olduğu commit (>0 → divergence)
  ```
  - `@..$REMOTE/$BR` sayısı `0` → fast-forward; doğrudan push.
  - `>0` → divergence; rebase gerekir. **`2>/dev/null` ile hatayı yutup 0 = "diverge yok" SANMA** — komut başarısızsa "divergence bilinmiyor" de, push'u zorlamadan fetch+rebase yolundan git.
- **Rebase — SADECE local, push-edilmemiş commit'ler** (`@{u}..@` penceresi; pushed commit'e history-rewrite YOK):
  ```bash
  git rebase "$REMOTE/$BR"
  ```
  - Conflict (`CONFLICT (...)`) çıkarsa → **Faz 5'e devret** (kör çözme YOK). Güvenli kaçış her an: `git rebase --abort` (local, yıkıcı **değil**; pre-rebase HEAD'e döner).
- **Push (force YOK):**
  ```bash
  git push "$REMOTE" "$BR"                     # ilk push ise: git push -u "$REMOTE" "$BR"
  ```
  - **non-fast-forward reddi** gelirse (yarış: fetch'ten sonra başka session push'ladı) → **retry-once**:
    ```bash
    git fetch "$REMOTE" "$BR" && git rebase "$REMOTE/$BR" && git push "$REMOTE" "$BR"
    ```
    Bu tek seferlik retry de düşerse **iki ayrı moda göre** dallan (ikisini birden Faz 5'e gönderme):
    - **İçerik çakışması** (retry rebase'i `CONFLICT (...)` üretti; unmerged path var → `git diff --name-only --diff-filter=U` **boş DEĞİL**) → **Faz 5** (supervisor).
    - **Saf non-fast-forward yarışı** (retry rebase'i temizdi ama push yine reddedildi; working tree temiz, `git diff --name-only --diff-filter=U` **boş**) → supervisor'a gerek **YOK** (incelenecek çakışma yok). **DUR** ve kullanıcıya bildir: *"remote başka bir session tarafından eşzamanlı push'lanıyor (saf non-fast-forward yarışı, içerik çakışması YOK). Force kullanmıyorum. Birazdan tekrar `/devir-land` dene; local commit korunuyor."* (İsteğe bağlı: bu STOP'tan önce açık bir deneme-üst-sınırıyla tam bir fetch+rebase+push turu daha denenebilir — ama no-conflict durumda supervisor **asla** çağrılmaz.) `--force` ASLA.
- Temiz rebase + push OK → **Faz 6** (temiz land raporu).

### NEVER (başka session'a zarar verebilecek YASAK işlemler)
Hiçbiri çalıştırılmaz — her biri paralel (başka worktree/branch) veya skalar (linear) session'ın işini düşürebilir:
- `git push --force` / `git push -f` / `git push --force-with-lease` — paylaşılan/push-edilmiş history'yi yeniden yazar, başka session'ın commit'lerini siler. **ASLA.**
- `git add -A` / `git add -u` / `git add .` — kör stage; alakasız/paralel WIP'i sızdırır. Sadece **explicit pathspec**.
- `git add -p` / `git add -i` — interaktif (stdin döngüsü); non-interaktif agent ortamında desteklenmez → hang/error. Kısmi-dosya için Faz 2'deki non-interaktif patch yolu (`git diff > patch` → Edit → `git apply --cached`) veya "dilim kapalı değil → DUR".
- `git reset --hard <ref>` — *(yıkıcı; mistype = veri kaybı)* working tree + index'i kaybeder. Paylaşılan branch'te asla.
- `git rebase` / `git commit --amend` / `git rebase -i` ile **zaten push edilmiş** commit'leri yeniden yazmak — yalnız `@{u}..@` (push-edilmemiş local) rebase edilebilir.
- `git checkout --theirs/--ours <foreign dosya>` veya conflict'te **foreign hunk'ı atmak** — başka session'ın işini düşürür.
- Foreign dosyayı silmek/üzerine yazmak (`rm`, clobbering write) — dilime ait olmayan dosyaya dokunma.
- `git clean -fd` — *(yıkıcı; mistype = untracked kaybı)* paralel session'ın untracked WIP'ini siler.
- `git pull` (rebase'siz, merge-default) paylaşılan branch'e — istenmeyen merge commit'i; açık `fetch` + `rebase` kullan.
- Paylaşımlı tek-dosya index'i (ör. `MEMORY.md`) **elle Edit** etmek — race/torn-file; varsayılan `/devir-land` index'e dokunmaz, olağanüstü durumda `~/.claude/hooks/devir_memory.py upsert` (flock + atomik).

> Genel ilke (DESIGN §4): **additive, non-destructive, ask-on-ambiguity.** Bir işlem başka session'ın bir hunk'ını/commit'ini/dosyasını **düşürebiliyorsa** → yapma, Faz 5'e götür.

## Faz 5 — Conflict supervision (devir noktası: bağlam → Opus subagent → verdict gate)
**Tetik (yalnız İÇERİK çakışması):** Faz 4'te (ilk rebase VEYA retry-once rebase) `CONFLICT (...)` çıkması — yani unmerged path var (`git diff --name-only --diff-filter=U` boş **DEĞİL**). Saf non-fast-forward push reddi (çakışma yok) bu faza **girmez** — Faz 4'teki "eşzamanlı push yarışı" STOP'una gider.

### 5a — Mekanik conflict bağlamı topla (önce — kör çözme/kör sorma YOK)
**Önce çakışma var mı doğrula:** `git --no-pager diff --name-only --diff-filter=U` **boşsa** → bu bir çakışma DEĞİL → supervisor yolunu **iptal et**, Faz 4'teki eşzamanlı-push STOP mesajına düş (force YOK, tekrar `/devir-land` öner). Boş değilse bağlamı topla.
Tümü `--no-pager`, çıktılar **verbatim**:
```bash
git --no-pager diff --name-only --diff-filter=U      # çatışan dosyalar (boşsa = çakışma yok → supervisor'ı çağırma)
git --no-pager diff                                   # birleşik conflict hunk'ları (<<<<<<< / ======= / >>>>>>>)
git --no-pager log --oneline "$REMOTE/$BR"..@ 2>/dev/null \
  || echo "(MINE penceresi bilinmiyor — upstream/rebase durumu)"   # MINE: benim local commit'lerim
git --no-pager log --oneline @.."$REMOTE/$BR" 2>/dev/null \
  || echo "(THEIRS bilinmiyor — boş = no-foreign SANMA)"            # THEIRS: remote/foreign commit'ler — KİMİN işi?
git status --short                                     # UU/AA/DU/UD marker'ları (kim-ne-yaptı)
```
> **`@{u}` KULLANMA** (hem upstream yokken hem de rebase sürerken detached HEAD'de `fatal` verir) → Faz 4'te türetilen remote-tracking ref `$REMOTE/$BR` kullan (rebase sırasında geçerli). **`@{u}`/ref hatasını yutup boş THEIRS = no-foreign SANMA** (Faz 4 line ile aynı kural) — log alınamadıysa supervisor'a **"THEIRS bilinmiyor"** olarak ilet, foreign-yok varsayma (downgrade-to-escalate).
Her çatışan dosyayı **DOMAIN sınıflandır** (Faz 2 pathspec'ine göre):
- **MINE** — Faz 2 pathspec'inde var (benim dilimimin kendi dosyası).
- **FOREIGN** — pathspec'imde yok → başka session'ın territory'si. *Tek bir FOREIGN bile = otomatik kullanıcı onayı (5c).*
- Gerekirse çatışan dosyayı `Read` ile aç → supervisor'a tam marker bloklarını ver.

### 5b — Opus supervisor subagent'ı spawn et (Task — READ-ONLY analiz)
Çatışmayı **kendin** sınıflandırma. Faz 5a bağlamını bir **Opus supervisor subagent**'a ver (`Task` tool; prompt'ta **"Opus modeli ile çalış, READ-ONLY analiz"** belirt). Subagent **SADECE analiz eder + önerir; UYGULAMAZ** (hiçbir dosya değiştirmez, hiçbir git komutu çalıştırmaz). Tek yazıcı = ana skill (single-writer; DESIGN §4a — paylaşılan worktree'de iki yazıcı = race + geri-alınamaz yabancı-hunk kaybı).

**Subagent'a verilen input (literal, paraphrase ETME):** dilim pathspec listesi (MINE kümesi) · her çatışan dosyanın MINE/FOREIGN etiketi · tam conflict hunk'ları + marker blokları · iki yönlü divergent log (MINE/THEIRS) + `git status --short`.

**Subagent talimatı (birebir):**
> Sen bir merge-conflict SUPERVISOR'ısın. Sana bir git rebase/merge çatışmasının mekanik bağlamı veriliyor. **Hiçbir dosyayı değiştirme, hiçbir git komutu çalıştırma** — sadece analiz et ve aşağıdaki şemada yapılandırılmış bir verdict döndür. En önemli kural: **hiçbir yabancı (FOREIGN) hunk veya yabancı commit'in işi DÜŞÜRÜLMEMELİDİR.** Emin değilsen sınıfı yukarı çek (downgrade-to-escalate). Yalnızca SIMPLE verdict'te kesin/mekanik bir çözüm öner.

**Subagent'ın döndüreceği şema (zorunlu alanlar):**
```
classification: SIMPLE | MEDIUM | HIGH | UNCERTAIN
foreign_involved: yes | no            # çatışan dosyalardan herhangi biri FOREIGN mi
foreign_work_dropped: yes | no | n/a  # önerilen çözüm yabancı satır/commit işini atar mı
reasoning: <2-4 cümle: neyle (hangi commit/kim) neden çakıştı>
# SADECE classification == SIMPLE ise:
resolution:
  - file: <yol>
    keep: <ours | theirs | both | additive-merge>
    merged_content: <conflict marker'ları TEMİZLENMİŞ tam içerik VEYA satır-kesin edit talimatı>
```
**Sınıflandırma rubriği:** **SIMPLE** = çatışma sadece MINE dosyalarında · mekanik/additive · hiçbir yabancı iş düşmez (ör. iki taraf ayrık/disjoint satır eklemiş → ikisini tut; import/CHANGELOG ayrı madde). **MEDIUM** = aynı bölgeye iki düzenleme, riskli ama yıkıcı değil. **HIGH** = bir tarafın işini ezme riski / silme-vs-düzenleme (DU/UD) / şema-migration. **UNCERTAIN** = niyet/güvenli birleştirme çıkarılamıyor. **Sabit kural:** `foreign_involved == yes` ise sınıf ne olursa olsun SIMPLE muamelesi GÖRMEZ → escalate. `foreign_work_dropped` riski → otomatik HIGH.

### 5c — Verdict kapısı (hiçbir şey uygulanmadan karar)
- **SIMPLE** — *yalnızca* tüm şu koşullar: subagent emin **VE** çatışma yalnız MINE dosyalarında (`foreign_involved == no`) **VE** çözüm mekanik/additive **VE** hiçbir yabancı iş düşmüyor (`foreign_work_dropped` ∉ {yes, risk}) →
  1. Çözümü **ana skill** uygular: çatışan dosyayı `Read` → conflict marker'larını (`<<<<<<<`/`=======`/`>>>>>>>`) temizle → `resolution.merged_content`'i yaz (`Edit`).
  2. Çözülen dosyayı **açık pathspec** ile stage: `git add -- <çözülen MINE dosyaları>` (yine `-A`/`-u` YOK) → `git rebase --continue`. Yeni conflict çıkarsa → 5a'ya dön (her hunk ayrı tur).
  3. Conflict bitince push: `git push "$REMOTE" "$BR"` (force YOK; reject → retry-once, Faz 4 kuralı).
  4. Kullanıcıya **RAPOR ET** — ne çakıştı + tam olarak nasıl çözüldü + **ham hatayı/conflict marker'ını da belirt** (kullanıcı görsün). SIMPLE'da bile conflict **mutlaka raporlanır** — sessizce çözme.
- **MEDIUM / HIGH / UNCERTAIN**, VEYA çatışma **herhangi bir FOREIGN dosyaya** dokunuyor (`foreign_involved == yes`), VEYA yabancı iş düşürme riski **var** → **ESCALATE:**
  - Hiçbir şey **uygulama** (edit yok, add yok, `rebase --continue` yok). Supervisor analizini + seçenekleri sun, **açık kullanıcı onayı bekle**:
    ```
    ⚠ Conflict — supervisor verdict: <MEDIUM/HIGH/UNCERTAIN | FOREIGN-file>
    Çatışan dosya(lar): <yol> (<MINE/FOREIGN>)
    Kiminle/hangi commit: <THEIRS log'undan SHA + konu>
    Supervisor analizi: <reasoning>
    Risk: <yabancı iş düşebilir mi / belirsizlik>
    Seçenekler:
     [1] <ours tut> · [2] <theirs tut> · [3] <manuel birleştir — önerilen merged içerik> · [4] git rebase --abort (land iptal)
    Hangisini uygulayayım? (onay olmadan dokunmuyorum)
    ```
  - **FOREIGN dosya conflict'i HER ZAMAN kullanıcı onayına çıkar** — ne kadar "basit" görünürse görünsün.
  - Kullanıcı bir seçenek onaylarsa → o çözümü ana skill uygular (5c-1..3 mekaniği), sonra raporla. Güvenli kaçış: `git rebase --abort` (local, yıkıcı değil).

> Kural: belirsizlik veya foreign-territory = **DUR ve SOR**. Emin + kendi-territory + additive = **çöz, devam et, raporla**.

## Faz 6 — Kapanış raporu (verbatim, ekrana)
**Temiz land (conflict yok):**
```
✅ Land tamam — <branch> → pushed (<SHA>)   |  (remote yoksa: yalnız local commit, push edilmedi)
Dilim: <dosya listesi>  |  Hedef PR: <# / yok / bilinmiyor>
Conflict: yok  |  Force-push: yok  |  Not'a/memory'ye dokunulmadı (süreklilik yok — bu bitmiş dilim).
YAPILMADI: handoff notu YOK · fresh session YOK · L1/L2 yazımı YOK.
```
**Conflict çıktı ve çözüldü (SIMPLE veya kullanıcı-onaylı):**
```
✅ Land tamam — <branch> → pushed (<yeni SHA>)
Dilim: <dosya listesi>  |  Hedef PR: <# / yok>
⚠ Conflict çıktı ve çözüldü:
  • Dosya: <yol> (MINE)
  • Kiminle: <THEIRS commit SHA + konu>  (rebase sırasında)
  • Ham hata/marker: "<git'in verdiği satır — ör. CONFLICT (content): Merge conflict in ...>"
  • Nasıl çözüldü: <both-added disjoint → ikisi tutuldu / ours / theirs / additive-merge>  (supervisor: SIMPLE | kullanıcı-onaylı)
  • Hiçbir yabancı (FOREIGN) iş düşürülmedi.
Not'a/memory'ye dokunulmadı (süreklilik yok).
```
- Branch'in **açık devir notu** varsa ve dilim onu açıkça bitiriyorsa → kullanıcıya yalnızca **belirt**: *"branch'in açık devir notu var; istersen `/devir-resume` ile consume edebilir veya elle `consumed` yapabilirsin — `/devir-land` nota dokunmadı."*

---
**Güvenlik özeti:** Tek yazıcı = ana skill; supervisor subagent READ-ONLY (geri-alınabilir öneri, atomik tek-uygulayıcı → paralel-session-güvenli). Onay noktaları: commit öncesi (#1) · push öncesi (#2) · her escalate'te uygulama öncesi. SIMPLE-auto yolu bu onayları **atlamaz** — yalnız conflict çözümünü otomatikleştirir; Faz 2/3 onayları yine geçerli. `/devir-land` saf entegrasyondur: not yazmaz, memory'ye dokunmaz, fresh session açmaz. Yarım iş için → **`/devir`**. Gerekçe: [`../devir/DESIGN.md`](../devir/DESIGN.md).
