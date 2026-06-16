---
name: devir-archive
description: Harcanmış (consumed/superseded) ve bayat (uzun süre dokunulmamış open/draft) devir notlarını paylaşılan devir-notes dizininden archive/ alt-dizinine MANUEL ve NON-DESTRUCTIVE taşı (mv — asla rm; archive/'den geri mv ile dönülebilir). Taze open/draft notlara DOKUNMAZ; her taşıma kullanıcı onayıyla, sessizce taşıma YOK. /devir ve /devir-resume'ün arşiv-hijyeni tümleyeni — SessionStart advisory-banner "arşiv adayı" uyarısının manuel karşılığı. Kullanıcı "devir notlarını arşivle", "eski/harcanmış notları temizle", "arşiv adaylarını taşı" derse. Mimari — ../devir/DESIGN.md §3.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(python3:*), Bash(mv:*), Bash(mkdir:*), Bash(ls:*), Bash(date:*), Read
---

# /devir-archive — devir notlarını güvenle arşivle (manuel · non-destructive)

Paylaşılan `devir-notes/` dizini zamanla **harcanmış** (resume edilmiş) ve **bayat** notlarla
şişer; SessionStart banner'ı bunu "🗄️ Arşiv adayı: …" diye bildirir. Bu skill o uyarının
**manuel, geri-dönülebilir** karşılığıdır: adayları gösterir, **kullanıcıya sorar**, seçilenleri
`archive/` alt-dizinine **taşır** (asla silmez). Scan zaten `archive/`'e bakmadığından taşınan
not banner/resume taramasından düşer ama **diskte kalır**. Mimari: [`../devir/DESIGN.md`](../devir/DESIGN.md) §3.

> **Değişmez ilkeler** (DESIGN §3 · `/devir-resume` Faz 6 ile uyumlu):
> - **Arşivleme HER ZAMAN manuel + kullanıcı kararı.** Bu skill `disable-model-invocation: true` — yalnız kullanıcı çağırır.
> - **Non-destructive:** `mv` (asla `rm`). `archive/`'den geri `mv` ile **tam geri-dönülebilir**.
> - **Taze open/draft notlara DOKUNMA** — yaş-cutoff yalnız *advisory* sinyalidir; geçerli bir branch'in notu haftalarca açık kalabilir. open/draft yalnız kullanıcı **açıkça** "hâlâ geçerli değil" onayı verince taşınır.

## Faz 1 — Dizini bul (anchor)
Notlar **ana checkout**ta toplanır (paylaşılan + kalıcı). Linked worktree'den bile ana köke çapala:
```bash
GCD="$(git rev-parse --git-common-dir 2>/dev/null)"; [ -z "$GCD" ] && { echo "git repo değil"; exit 0; }
case "$GCD" in /*) ;; *) GCD="$PWD/$GCD" ;; esac
MAIN_ROOT="$(cd "$(dirname "$GCD")" && pwd)"
NOTES_DIR="$MAIN_ROOT/.claude/docs/devir-notes"
ARCHIVE_DIR="$NOTES_DIR/archive"
[ -d "$NOTES_DIR" ] || { echo "not dizini yok — arşivlenecek bir şey yok"; exit 0; }
```

## Faz 2 — Adayları kovala (status + yaş)
`$NOTES_DIR`'deki `*.md` dosyalarını (alt-dizin `archive/` HARİÇ) frontmatter `status` + dosya
**mtime** ile oku. İki kova:
- **spent** = `status: consumed` veya `superseded` — **kesin aday** (iş resume edildi / üstüne yazıldı).
- **stale** = `status: open|draft` ama mtime **>14 gün** (banner eşiği `ARCHIVE_ADVISORY_DAYS`) — **yalnız ipucu**; taşımak için ekstra onay.
- **ACTIVE** = taze (≤14g) open/draft → **aday DEĞİL, gösterme/dokunma.**

Mekanik oku (sıralı, kovalı):
```bash
for f in "$NOTES_DIR"/*.md; do [ -f "$f" ] || continue
  st=$(awk -F': *' '/^status:/{print $2; exit}' "$f")
  age_d=$(( ( $(date +%s) - $(stat -f %m "$f") ) / 86400 ))   # macOS stat; Linux: stat -c %Y
  printf '%s\t%s\t%sg\t%s\n' "$st" "$age_d" "$age_d" "$(basename "$f")"
done
```
(Tarih komutu OS'a göre: macOS `stat -f %m`, GNU `stat -c %Y`. Hata olursa o dosyayı atla, çökme.)

## Faz 3 — Sun + SOR (sessizce taşıma YOK)
Adayları **numaralı + kovalı** sun; **hiçbirini varsayılan seçme**:
```
Arşiv adayları (devir-notes/ → archive/, geri-dönülebilir):
  spent (harcanmış — güvenli):
   [1] <id>  <branch>  status=consumed
  stale (>14g dokunulmamış — teyit gerek):
   [2] <id>  <branch>  status=open  (32g)
Hangilerini arşivleyeyim? (numara/aralık · "spent" = tüm harcanmışlar · "iptal")
```
- **stale (open/draft) seçilirse:** taşımadan önce **tek tek** "Bu not hâlâ geçerli değil, arşivlensin mi?" diye teyit al — kör taşıma yok.
- Hiç aday yoksa: "Arşivlenecek aday yok — dizin temiz." de, çık.

## Faz 4 — Taşı (non-destructive, reversible)
Yalnız **onaylanan** dosyalar için:
```bash
mkdir -p "$ARCHIVE_DIR"
mv "$NOTES_DIR/<seçilen>.md" "$ARCHIVE_DIR/"     # asla rm; git mv DEĞİL (notlar gitignored)
```
- `git mv` **kullanma** — notlar varsayılan gitignored, untracked; düz `mv` doğru. (Repo'daki *tracked örnek* not zaten `archive/`'de; ona dokunma.)
- Frontmatter `status`'u **değiştirme** — arşiv = konum kararı, lifecycle değil; geri alınırsa not aynen döner.

## Faz 5 — Raporla + geri-alma
Ne taşındığını, `archive/` yolunu ve **geri-alma** komutunu ver:
```
✓ 2 not arşivlendi → <ARCHIVE_DIR>/
  Geri al:  mv "<ARCHIVE_DIR>/<id>.md" "<NOTES_DIR>/"
```
- **Commit etme/erteleme:** notlar gitignored → arşiv taşıması git'e girmez, commit gerekmez. (Yalnız kullanıcı *tracked* örnek notu taşıdıysa `git mv` + onaylı commit; AI co-author trailer YOK.)
- Tek seferde değerlendir; sonraki `/devir` bağımsız çalışır — bu skill state/memory'ye dokunmaz.

---
**Not:** Arşivleme bir **hijyen** adımıdır, süreklilik değil — L1 memory + L2 not yaşam döngüsünü
(`draft→open→consumed`) değiştirmez; yalnız spent/bayat notların **fiziksel konumunu** kullanıcı
onayıyla `archive/`'e taşır. SessionStart "arşiv adayı" banner'ı bu skill'i önerir; otomatik taşıyıcı **DEĞİL**.
