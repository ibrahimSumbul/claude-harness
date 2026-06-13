#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook — context ~260k'yı aşınca /devir'i tetikler (advisory).

Global: ~/.claude/settings.json üzerinden TÜM Claude Code session'larında çalışır.
ADVISORY: hook bir shell komutu; modeli zorla skill çalıştıramaz (Anthropic #43733). Eşik
aşılınca modele 'şimdi /devir çalıştır' talimatını ENJEKTE eder (additionalContext). Model
genelde uyar, garanti değil → deterministik ağ ayrı: devir-precompact.py + devir-sessionstart.py.
Mimari: ~/.claude/skills/devir/DESIGN.md
"""
import sys, json, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import devir_common as dc
except Exception:
    dc = None

THRESHOLD = 260_000           # /devir tetik eşiği — ~300k degradation öncesi (gözlem: 282k spike).
REFIRE_GAP = 20_000           # ilk uyarı görmezden gelinirse +bu kadar token sonra tekrar
CLEANUP_DAYS = 7              # .devir-state'te bu kadar günden eski marker temizlenir
NOTE_FRESH_HOURS = 6          # bu süre içinde açık/taze not yoksa "not oluştur" hatırlat
STATE_DIR = os.path.expanduser("~/.claude/.devir-state")


def estimate_tokens(path):
    if dc is not None:
        try:
            return dc.latest_usage_tokens(path)
        except Exception:
            pass
    try:
        return os.path.getsize(path) // 4
    except Exception:
        return 0


def cleanup_old_markers():
    try:
        cutoff = time.time() - CLEANUP_DAYS * 86_400
        for name in os.listdir(STATE_DIR):
            if not (name.endswith(".fired") or name.endswith(".consumed.md")
                    or name.endswith(".dump.md")):
                continue
            p = os.path.join(STATE_DIR, name)
            try:
                if os.path.getmtime(p) < cutoff:
                    os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def has_recent_note(cwd):
    """Bu worktree için son NOTE_FRESH_HOURS içinde yazılmış açık not var mı?"""
    if not dc:
        return False
    try:
        cutoff = time.time() - NOTE_FRESH_HOURS * 3_600
        for n in dc.scan_notes(cwd, statuses=("open", "draft")):
            wt = (n["fm"].get("worktree") or "")
            if dc.under_worktree(cwd, wt) and n["mtime"] >= cutoff:
                return True
    except Exception:
        return False
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    transcript = data.get("transcript_path")
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd") or os.getcwd()
    if not transcript or not os.path.isfile(transcript):
        return

    tokens = estimate_tokens(transcript)
    if tokens < THRESHOLD:
        return

    # once-per-session + refire guard (nag yapma)
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        marker = os.path.join(STATE_DIR, f"{session_id}.fired")
        last = 0
        if os.path.exists(marker):
            try:
                last = int((open(marker).read().strip() or "0"))
            except Exception:
                last = 0
        if last and tokens < last + REFIRE_GAP:
            return
        with open(marker, "w") as m:
            m.write(str(tokens))
        cleanup_old_markers()
    except Exception:
        pass  # marker yazılamasa bile uyarıyı ver

    msg = (
        f"⚠️ Bu Claude Code session'ı ~{tokens:,} token (≥{THRESHOLD:,} eşiği — long-context "
        "degradation bölgesine yaklaşıyor). Kullanıcının mevcut mesajını ele almadan ÖNCE "
        "`/devir` skill'ini çalıştır: canlı git state yakala → L1 memory (session-state-<branch>) "
        "+ L2 git-tracked unique-ID not (.claude/docs/devir-notes/) üret → MEMORY.md'yi "
        "devir_memory.py helper ile güncelle → verbatim handoff + git commit kapanışı → "
        "kullanıcıya YENİ session açmasını söyle."
    )
    if not has_recent_note(cwd):
        msg += " (Bu worktree için taze açık devir notu yok.)"
    msg += (" Not: compaction öncesi mekanik PreCompact draft ağı da var ama lossy — temiz devir "
            "için şimdi /devir çalıştırmak daha iyi.")

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": msg,
    }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
