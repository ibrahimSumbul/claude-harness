#!/usr/bin/env python3
"""Claude Code SessionStart hook — devir state'ini yeni context'e geri enjekte eder (v2).

- source=compact  → AYNI session compact oldu. Bu worktree'nin en iyi notunun (open>draft) ▶ RESUME
  bölümünü additionalContext olarak AUTO-INJECT eder → insan-yok compaction anında hands-free
  recovery (gap-4). Not yoksa ephemeral dump'a düşer.
- source=startup/resume → DURUM BANNER'ı (Roo pattern): bu worktree için açık not sayısını bildirir;
  1 ise RESUME özetini + `/devir-resume` önerir, ≥2 ise "seç" der (sessizce SEÇMEZ, consume ETMEZ).
- source=clear → no-op.

Birincil süreklilik yine L1 memory auto-recall'da; bu ek ağ. Her hata → boş çıktı (session'ı kırma).
Mimari: ~/.claude/skills/devir/DESIGN.md
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import devir_common as dc
except Exception:
    dc = None

STATE_DIR = os.path.expanduser("~/.claude/.devir-state")
INJECT_CAP = 1_400             # enjekte edilen metin max karakter
# Not: open/draft statüsü lifecycle sinyali; git-tracked notlara yaş cutoff'u UYGULANMAZ
# (haftalarca açık kalan bir branch'in notu hâlâ geçerli olabilir).


def emit(context):
    if not context:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, ensure_ascii=False))


def extract_section(text, names):
    """Başlığında `names`'ten biri geçen section'ı (heading + altı) çek.

    FENCE-AWARE: ``` kod bloğu içindeki `#` satırları markdown başlığı DEĞİL (shell
    yorumu) — section'ı orada kesme. RESUME bloğu `# İlk aksiyon: ...` shell-comment'i
    içerir; fence-bilinçsiz tarama tam o kritik satırda break ederdi.
    """
    out, capturing, in_fence = [], False, False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            if capturing:
                out.append(ln)
            continue
        if not in_fence and s.startswith("#"):
            low = s.lower()
            if any(n in low for n in names):
                capturing = True
                out.append(ln)
                continue
            if capturing:
                break
        if capturing:
            out.append(ln)
    return "\n".join(out).strip()


def worktree_notes(cwd):
    """Bu worktree için açık (open/draft) notlar, open önce sonra mtime DESC."""
    if not dc:
        return []
    res = []
    try:
        for n in dc.scan_notes(cwd, statuses=("open", "draft")):
            if dc.under_worktree(cwd, n["fm"].get("worktree") or ""):
                res.append(n)
    except Exception:
        return []
    # nested worktree: parent worktree'nin notlarını cross-match etme — kendi repo köküne öncelik
    try:
        own = os.path.realpath(dc.repo_root(cwd) or cwd)
        exact = [n for n in res if os.path.realpath(n["fm"].get("worktree") or "") == own]
        if exact:
            res = exact
    except Exception:
        pass
    res.sort(key=lambda x: (dc.STATUS_RANK.get((x["fm"].get("status") or "").lower(), 0), x["mtime"]),
             reverse=True)
    return res


def read_dump(path):
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def main():
    if not dc:
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    source = data.get("source", "")
    session_id = data.get("session_id", "")
    cwd = data.get("cwd") or os.getcwd()

    if source == "clear":
        return

    # --- AYNI session compact oldu: en iyi notun RESUME'unu auto-inject ---
    if source == "compact":
        notes = worktree_notes(cwd)
        if notes:
            cur_branch = dc.git(["branch", "--show-current"], cwd)
            same = [n for n in notes if (n["fm"].get("branch") or "") == cur_branch]
            branches = {(n["fm"].get("branch") or "") for n in notes}
            if same:
                best = same[0]
            elif len(branches) > 1:
                emit("🔄 Session compact'landı; bu worktree'de BİRDEN FAZLA branch'te açık not var — "
                     "otomatik seçmedim. Doğru olanı `/devir-resume` ile seç.")
                return
            else:
                best = notes[0]
            fm, text = dc.read_note(best["path"])
            section = extract_section(text, ["resume"]) or extract_section(text, ["yapılan", "git status"])
            if len(section) > INJECT_CAP:
                section = section[:INJECT_CAP] + "\n…(kısaltıldı)"
            emit(
                f"🔄 Session compact'landı. Bu worktree'nin devir notu (`{fm.get('status','?')}`, "
                f"`{best['path']}`) — süreklilik için geri yüklendi:\n\n{section}\n\n"
                "Belirsizse kullanıcıya kaldığınız yeri teyit ettir; yıkıcı aksiyon öncesi "
                "`/devir-resume` ile onay al."
            )
            return
        # fallback: bu session'ın ephemeral dump'ı
        text = read_dump(os.path.join(STATE_DIR, f"{session_id}.dump.md"))
        if text:
            if len(text) > INJECT_CAP:
                text = text[:INJECT_CAP] + "\n…(kısaltıldı)"
            emit("🔄 Session compact'landı. Mekanik PreCompact dump:\n\n" + text
                 + "\n\nTemiz handoff için `/devir`.")
        return

    # --- Yeni/devam session: durum banner'ı (consume ETME) ---
    if source in ("startup", "resume"):
        notes = worktree_notes(cwd)
        if not notes:
            emit("🧭 DEVIR: bu worktree için açık devir notu yok. (Süreklilik L1 memory'de — "
                 "resume için memory session-state'e bak.)")
            return
        if len(notes) == 1:
            fm, text = dc.read_note(notes[0]["path"])
            resume = extract_section(text, ["resume"])
            head = (f"🧭 DEVIR: `{fm.get('branch','?')}` için 1 açık not var "
                    f"(`{fm.get('status','?')}`, id `{fm.get('id','?')}`). `/devir-resume` ile devam et.")
            if resume:
                if len(resume) > INJECT_CAP:
                    resume = resume[:INJECT_CAP] + "\n…(kısaltıldı)"
                head += "\n\n" + resume
            emit(head)
            return
        # ≥2 → seçtirme, SOR
        lines = ["🧭 DEVIR: bu worktree için BİRDEN FAZLA açık not var — `/devir-resume` ile seç (sessizce seçme):"]
        for n in notes[:6]:
            fm = n["fm"]
            lines.append(f" • `{fm.get('branch','?')}`  ({fm.get('status','?')}, id `{fm.get('id','?')}`, {fm.get('created','?')})")
        emit("\n".join(lines))
        return


if __name__ == "__main__":
    main()
