#!/usr/bin/env python3
"""Claude Code PreCompact hook — compaction'dan HEMEN ÖNCE deterministik state dump (v2).

/devir nudge ADVISORY (model uyabilir/uymaz). Bu hook o boşluğu kapatır: model işbirliği
GEREKMEDEN, compaction başlamadan canlı git state + dokunulan dosyalar + (opsiyonel) son
alışverişi yakalar. İKİ çıktı:
  1) Ephemeral dump  ~/.claude/.devir-state/<session>.dump.md   (her zaman; repo olmasa da)
  2) Git-tracked DRAFT not  <repo>/.claude/docs/devir-notes/<id>.md  (repo varsa; open not yoksa)

GİZLİLİK: ham mesaj yakalama opt-in (default KAPALI; ~/.claude/devir.config.json
capture_raw_messages=true ile aç) + her zaman secret redaction.
Bloke ETMEZ — her hata exit 0 → compaction asla kırılmaz.
stdin JSON: session_id, transcript_path, cwd, trigger ("manual"|"auto").
"""
import sys, os, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import devir_common as dc
except Exception:
    dc = None

STATE_DIR = os.path.expanduser("~/.claude/.devir-state")


def has_open_supersede(cwd, branch):
    """Bu branch/worktree için zaten 'open' not var mı? Varsa draft yazma (open supersedes)."""
    if not dc:
        return False
    try:
        for n in dc.scan_notes(cwd, statuses=("open",)):
            fm = n["fm"]
            if (fm.get("branch") or "") == branch and dc.under_worktree(cwd, fm.get("worktree") or ""):
                return True
    except Exception:
        return False
    return False


def main():
    if not dc:
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cwd = data.get("cwd") or os.getcwd()
    session_id = data.get("session_id", "unknown")
    transcript = data.get("transcript_path")
    trigger = data.get("trigger", "?")

    cfg = dc.load_config()
    redact = cfg.get("redact_patterns", [])
    capture_raw = cfg.get("capture_raw_messages", False)

    toplevel = dc.repo_root(cwd)
    branch = dc.git(["branch", "--show-current"], cwd) if toplevel else ""
    status = dc.git(["status", "--short"], cwd) if toplevel else ""
    log5 = dc.git(["--no-pager", "log", "--oneline", "-5"], cwd) if toplevel else ""
    branch_work = dc.git(["--no-pager", "log", "--oneline", "main..HEAD"], cwd) if toplevel else ""
    uncommitted = "yes" if status else "no"

    tokens = 0
    last_user = last_assistant = ""
    touched = []
    if transcript and os.path.isfile(transcript):
        try:
            tokens = dc.latest_usage_tokens(transcript)
            touched = dc.touched_files_from_transcript(transcript)
            if capture_raw:
                last_user, last_assistant = dc.last_messages(transcript, redact_patterns=redact)
        except Exception:
            pass

    # redaction (her zaman)
    status = dc.redact_text(status, redact)
    log5 = dc.redact_text(log5, redact)
    branch_work = dc.redact_text(branch_work, redact)
    last_user = dc.redact_text(last_user, redact)
    last_assistant = dc.redact_text(last_assistant, redact)
    touched = [dc.redact_text(p, redact) for p in touched]

    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        created = datetime.now().astimezone().isoformat(timespec="seconds")
    except Exception:
        ts = created = "?"

    touched_block = "\n".join(f"- {p}" for p in touched) if touched else "(yok)"

    # --- 1) Ephemeral dump (her zaman) ---
    dump_lines = [
        f"# DEVİR AUTO-DUMP (PreCompact, trigger={trigger}) — {ts}",
        "",
        f"- session: `{session_id}`",
        f"- cwd: `{cwd}`",
        f"- worktree: `{toplevel or '(git repo değil)'}`",
        f"- branch: `{branch}`  |  uncommitted: **{uncommitted}**  |  ~{tokens:,} token",
        "",
        "## git status --short", "```", status or "(temiz)", "```",
        "## son commitler (log -5)", "```", log5 or "(yok)", "```",
        "## bu branch'te yapılan iş (main..HEAD)", "```", branch_work or "(main ile aynı / yok)", "```",
        "## dokunulan dosyalar (tool-input'tan)", touched_block,
    ]
    if capture_raw and last_user:
        dump_lines += ["## son user mesajı (redacted, kısaltılmış)", "```", last_user, "```"]
    if capture_raw and last_assistant:
        dump_lines += ["## son assistant metni (redacted, kısaltılmış)", "```", last_assistant, "```"]
    if not capture_raw:
        dump_lines += ["## ham mesaj", "- disabled (opt-in: devir.config.json capture_raw_messages=true)"]
    dump_lines += ["", "> ⚠️ MEKANİK dump (model üretmedi). Temiz handoff için fresh session'da `/devir`."]
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, f"{session_id}.dump.md"), "w") as f:
            f.write("\n".join(dump_lines) + "\n")
    except Exception:
        pass

    # --- 2) Git-tracked DRAFT not (repo varsa + open not yoksa) ---
    if not toplevel or has_open_supersede(cwd, branch):
        return
    try:
        import hashlib
        # session başına TEK draft (tekrarlı compact aynı dosyayı günceller); çarpışmaya dayanıklı tag.
        session_tag = hashlib.sha1((session_id or "sess").encode("utf-8")).hexdigest()[:8]
        note_id = f"{datetime.now().strftime('%Y-%m-%d')}-{dc.slugify(branch)}-draft-{session_tag}"
        nd = dc.notes_dir(cwd)
        os.makedirs(nd, exist_ok=True)
        note_path = os.path.join(nd, f"{note_id}.md")
        note = [
            "---",
            f"id: {note_id}",
            f"session_id: {session_id}",
            f"branch: {branch}",
            f"worktree: {toplevel}",
            f"created: {created}",
            "status: draft",
            f"tokens: {tokens}",
            "covers_since: session start",
            "---",
            f"# DEVİR DRAFT — {note_id}",
            "",
            "> Kaynak: `PreCompact` hook (otomatik, mekanik). *Tam devir değil* — fresh session'da",
            "> `/devir` ile `▶ RESUME`'u netleştir veya `/devir-resume` ile bu draft'tan devam et.",
            "",
            "## Yapılan (main..HEAD)", "```", branch_work or "(main ile aynı / yok)", "```",
            "## git status --short", "```", status or "(temiz)", "```",
            "## son commitler", "```", log5 or "(yok)", "```",
            "## dokunulan dosyalar", touched_block,
        ]
        if capture_raw and last_user:
            note += ["## son user mesajı (redacted)", "```", last_user, "```"]
        if not capture_raw:
            note += ["## ham mesaj", "- disabled (opt-in gerekli)"]
        note += [
            "## ▶ RESUME",
            "- [ ] MEKANİK draft — `/devir` ile net RESUME satırı + literal komut bloğu yaz.",
        ]
        with open(note_path, "w") as nf:
            nf.write("\n".join(note) + "\n")
    except Exception:
        pass  # yazılamasa bile compaction'ı kırma


if __name__ == "__main__":
    main()
