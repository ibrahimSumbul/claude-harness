#!/usr/bin/env python3
"""devir v2 uçtan-uca test harness.

Tek-kullanımlık geçici git repo kurar, L3 hook'larını gerçek harness JSON
payload'larıyla (stdin) sürer, çıktıları assert eder. devir_common + devir_memory
düşük seviyesini de doğrular. Gerçek repolara DOKUNMAZ; STATE_DIR'e sadece fake
session-id'li ephemeral dosya yazar ve sonunda temizler.
"""
import json, os, subprocess, sys, tempfile, shutil, time

HOOKS = os.path.dirname(os.path.abspath(__file__))  # vendored kopyayı test et → fresh clone'da çalışır
sys.path.insert(0, HOOKS)
import devir_common as dc  # noqa

STATE_DIR = os.path.expanduser("~/.claude/.devir-state")
PASS, FAIL = [], []
FAKE_SESSIONS = []  # cleanup


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "✅" if cond else "❌"
    print(f"{mark} {name}" + (f"  — {detail}" if detail and not cond else ""))


def run_hook(script, payload):
    """Hook'u subprocess ile stdin JSON vererek çalıştır, stdout döndür."""
    p = subprocess.run(
        [sys.executable, os.path.join(HOOKS, script)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=20,
    )
    return p.stdout.strip(), p.stderr.strip(), p.returncode


def ctx(stdout):
    """SessionStart/UserPromptSubmit additionalContext'i çıkar."""
    if not stdout:
        return ""
    try:
        return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return f"<<unparseable: {stdout[:120]}>>"


def git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)


def write_note(nd, note_id, branch, worktree, status, resume_line, created=None):
    os.makedirs(nd, exist_ok=True)
    created = created or "2026-06-13T10:00:00+03:00"
    body = f"""---
id: {note_id}
branch: {branch}
worktree: {worktree}
created: {created}
status: {status}
tokens: 261000
covers_since: session start
---
# DEVİR — {note_id}
## Hedef
Test hedefi.
## ▶ RESUME
```bash
git -C "{worktree}" checkout {branch}
# İlk aksiyon: {resume_line}
```
"""
    with open(os.path.join(nd, f"{note_id}.md"), "w") as f:
        f.write(body)


def make_transcript(path, total_tokens):
    """Sonda verilen usage'ı taşıyan minimal transcript JSONL üret."""
    lines = [
        json.dumps({"type": "user", "message": {"role": "user",
                    "content": "merhaba dünya bu bir test"}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "text", "text": "cevap"},
                                {"type": "tool_use", "name": "Edit",
                                 "input": {"file_path": "/tmp/x/foo.py"}}],
                    "usage": {"input_tokens": total_tokens, "output_tokens": 10,
                              "cache_read_input_tokens": 0,
                              "cache_creation_input_tokens": 0}}}),
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    tmp = tempfile.mkdtemp(prefix="devir-e2e-")
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    try:
        # ---- repo kurulumu: main + feature branch (main..HEAD dolu olsun) ----
        git(["init", "-q", "-b", "main"], repo)
        git(["config", "user.email", "t@t.t"], repo)
        git(["config", "user.name", "t"], repo)
        with open(os.path.join(repo, "README.md"), "w") as f:
            f.write("base\n")
        git(["add", "."], repo)
        git(["commit", "-q", "-m", "init"], repo)
        git(["checkout", "-q", "-b", "feature/login"], repo)
        with open(os.path.join(repo, "login.py"), "w") as f:
            f.write("# wip\n")
        git(["add", "."], repo)
        git(["commit", "-q", "-m", "wip login"], repo)
        # kirli working tree (uncommitted sinyali)
        with open(os.path.join(repo, "dirty.txt"), "w") as f:
            f.write("uncommitted\n")

        nd = dc.notes_dir(repo)
        print(f"\n# repo={repo}\n# notes_dir={nd}\n# branch=feature/login\n")

        # ================= devir_common düşük seviye =================
        print("== devir_common ==")
        check("repo_root doğru", os.path.realpath(dc.repo_root(repo)) == os.path.realpath(repo))
        check("notes_dir repo altında",
              os.path.realpath(nd).startswith(os.path.realpath(repo)))
        check("under_worktree (alt-dizin)", dc.under_worktree(os.path.join(repo, "sub"), repo))
        check("under_worktree (symlink-norm /var)",
              dc.under_worktree("/tmp/zzz", "/private/tmp/zzz") or "/tmp" != os.path.realpath("/tmp"),
              "symlink normalize")
        check("under_worktree (alakasız yol reddedilir)", not dc.under_worktree("/etc", repo))
        check("slugify branch", dc.slugify("feature/Login Bug") == "feature-login-bug",
              dc.slugify("feature/Login Bug"))
        # redaction
        red = dc.redact_text("api_key=SECRET123 ghp_abcdefghijklmnop1234", dc.DEFAULT_REDACT_PATTERNS)
        check("redaction (api_key gizlendi)", "SECRET123" not in red, red)
        check("redaction (ghp token gizlendi)", "abcdefghijklmnop1234" not in red, red)
        jwt = dc.redact_text("token: eyJhbGciOiJIUzI1NiwidHlwIjoiSldUIn0extra", dc.DEFAULT_REDACT_PATTERNS)
        check("redaction (JWT gizlendi)", "[REDACTED]" in jwt, jwt)

        # token okuma (son-kazanır)
        tpath = os.path.join(tmp, "t.jsonl")
        make_transcript(tpath, 261_000)
        check("latest_usage_tokens=261000", dc.latest_usage_tokens(tpath) == 261_000,
              str(dc.latest_usage_tokens(tpath)))
        touched = dc.touched_files_from_transcript(tpath)
        check("touched_files çıkarıldı", "/tmp/x/foo.py" in touched, str(touched))

        # ================= SessionStart =================
        print("\n== devir-sessionstart.py ==")
        # S1: 0 not, startup
        out, err, rc = run_hook("devir-sessionstart.py", {"source": "startup", "cwd": repo})
        c = ctx(out)
        check("S1 startup/0-not → 'açık devir notu yok'", "açık devir notu yok" in c, c[:160])
        check("S1 exit 0", rc == 0)

        # S2: 1 open note matching branch
        write_note(nd, "2026-06-13-feature-login-aaa111", "feature/login", repo,
                   "open", "login testini koştur")
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "startup", "cwd": repo})
        c = ctx(out)
        check("S2 startup/1-not → '1 açık not'", "1 açık not" in c, c[:160])
        check("S2 RESUME satırı enjekte edildi", "login testini koştur" in c, c[:200])

        # S3 (v2.3 branch-match): login'deyken farklı-branch (signup) notu eklensin →
        # paylaşılan dizinde banner branch-match ile YALNIZ mevcut-branch notunu gösterir
        # (çapraz-branch notuyla karışmaz — eski worktree-match'te ikisi de listeleniyordu).
        write_note(nd, "2026-06-13-feature-signup-bbb222", "feature/signup", repo,
                   "open", "signup formu")
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "startup", "cwd": repo})
        c = ctx(out)
        check("S3 branch-match: çakışan branch notu varken yalnız mevcut-branch notu",
              "1 açık not" in c and "login testini koştur" in c and "signup formu" not in c, c[:240])

        # S3b: mevcut branch hiçbir notla eşleşmiyor + ≥2 açık not → BİRDEN FAZLA, sessizce seçmez
        git(["checkout", "-q", "-b", "feature/none"], repo)
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "startup", "cwd": repo})
        c = ctx(out)
        check("S3b eşleşme-yok/çoklu → 'BİRDEN FAZLA'", "BİRDEN FAZLA" in c, c[:160])
        check("S3b sessizce seçmiyor (notlar listelenir)",
              "feature/login" in c and "feature/signup" in c, c[:240])
        git(["checkout", "-q", "feature/login"], repo)

        # S4: compact, mevcut branch=feature/login → o notu auto-inject
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "compact", "cwd": repo})
        c = ctx(out)
        check("S4 compact → RESUME auto-inject (branch-match)",
              "compact" in c.lower() and "login testini koştur" in c, c[:220])

        # S5: compact, mevcut branch hiçbir notla eşleşmiyor + çoklu branch → seçtir
        git(["checkout", "-q", "-b", "feature/other"], repo)
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "compact", "cwd": repo})
        c = ctx(out)
        check("S5 compact/eşleşme-yok/çoklu-branch → otomatik seçmez",
              "BİRDEN FAZLA branch" in c or "otomatik seçmedim" in c, c[:200])
        git(["checkout", "-q", "feature/login"], repo)

        # S6: clear → no-op
        out, _, rc = run_hook("devir-sessionstart.py", {"source": "clear", "cwd": repo})
        check("S6 clear → boş çıktı (no-op)", out == "", out[:80])

        # S7: superseded/consumed notlar bannera girmez
        write_note(nd, "2026-06-13-feature-login-ccc333", "feature/login", repo,
                   "consumed", "eski iş")
        out, _, _ = run_hook("devir-sessionstart.py", {"source": "startup", "cwd": repo})
        c = ctx(out)
        check("S7 consumed not banner'a girmiyor", "eski iş" not in c, c[:200])

        # ================= autotrigger =================
        print("\n== devir-autotrigger.py ==")
        sess = "e2e-fake-autotrigger"
        FAKE_SESSIONS.append(sess)
        # eşik altı
        low = os.path.join(tmp, "low.jsonl"); make_transcript(low, 100_000)
        out, _, _ = run_hook("devir-autotrigger.py",
                             {"session_id": sess, "transcript_path": low, "cwd": repo})
        check("A1 eşik altı (100k) → tetiklenmez", out == "", out[:80])
        # eşik üstü → tetikle
        hi = os.path.join(tmp, "hi.jsonl"); make_transcript(hi, 265_000)
        out, _, _ = run_hook("devir-autotrigger.py",
                             {"session_id": sess, "transcript_path": hi, "cwd": repo})
        c = ctx(out)
        check("A2 eşik üstü (265k) → /devir nudge", "/devir" in c and "265,000" in c, c[:160])
        # hemen tekrar (refire guard, aynı token) → susmalı
        out, _, _ = run_hook("devir-autotrigger.py",
                             {"session_id": sess, "transcript_path": hi, "cwd": repo})
        check("A3 refire guard → ikinci kez susuyor", out == "", out[:80])
        # +25k → tekrar tetikle
        hi2 = os.path.join(tmp, "hi2.jsonl"); make_transcript(hi2, 290_000)
        out, _, _ = run_hook("devir-autotrigger.py",
                             {"session_id": sess, "transcript_path": hi2, "cwd": repo})
        check("A4 +25k sonrası → yeniden tetikler", "/devir" in ctx(out), ctx(out)[:120])

        # ================= precompact =================
        print("\n== devir-precompact.py ==")
        # feature/other branch'inde open not YOK → draft yazılmalı
        git(["checkout", "-q", "feature/other"], repo)
        psess = "e2e-fake-precompact"
        FAKE_SESSIONS.append(psess)
        ptrans = os.path.join(tmp, "pc.jsonl"); make_transcript(ptrans, 250_000)
        out, err, rc = run_hook("devir-precompact.py",
                                {"session_id": psess, "transcript_path": ptrans,
                                 "cwd": repo, "trigger": "auto"})
        check("P1 precompact exit 0 (compaction'ı kırmaz)", rc == 0, err[:120])
        dump = os.path.join(STATE_DIR, f"{psess}.dump.md")
        check("P2 ephemeral dump yazıldı", os.path.isfile(dump), dump)
        if os.path.isfile(dump):
            d = open(dump).read()
            check("P2b dump'ta git status var", "git status" in d)
            check("P2c dump'ta dokunulan dosya var", "foo.py" in d, "touched")
        # draft not (feature/other'da open yok)
        drafts = [n for n in os.listdir(nd) if "feature-other" in n and "draft" in n]
        check("P3 draft not üretildi (open yokken)", len(drafts) == 1, str(os.listdir(nd)))
        if drafts:
            dft = open(os.path.join(nd, drafts[0])).read()
            check("P3b draft status=draft", "status: draft" in dft)
            check("P3c draft RESUME placeholder/TODO içerir",
                  "RESUME" in dft and ("[ ]" in dft or "MEKANİK" in dft))
        # P4: feature/login'de open not VAR → precompact draft YAZMAMALI (open supersedes)
        git(["checkout", "-q", "feature/login"], repo)
        psess2 = "e2e-fake-precompact2"; FAKE_SESSIONS.append(psess2)
        before = set(os.listdir(nd))
        run_hook("devir-precompact.py",
                 {"session_id": psess2, "transcript_path": ptrans,
                  "cwd": repo, "trigger": "auto"})
        after = set(os.listdir(nd))
        new_login_drafts = [n for n in (after - before) if "feature-login" in n]
        check("P4 open not varken draft YAZILMADI (supersede)", new_login_drafts == [],
              str(new_login_drafts))
        # P5: repo değilken precompact patlamaz, dump yine yazılır
        nonrepo = os.path.join(tmp, "plain"); os.makedirs(nonrepo)
        psess3 = "e2e-fake-precompact3"; FAKE_SESSIONS.append(psess3)
        out, err, rc = run_hook("devir-precompact.py",
                                {"session_id": psess3, "transcript_path": ptrans,
                                 "cwd": nonrepo, "trigger": "manual"})
        check("P5 non-repo precompact exit 0", rc == 0, err[:120])
        check("P5b non-repo'da dump yine yazıldı",
              os.path.isfile(os.path.join(STATE_DIR, f"{psess3}.dump.md")))

        # ================= devir_memory upsert =================
        print("\n== devir_memory.py ==")
        mem = os.path.join(tmp, "MEMORY.md")
        with open(mem, "w") as f:
            f.write("# Memory Index\n\n- [Existing](existing.md) — eski\n")

        def upsert(key, line, maxl=200):
            return subprocess.run(
                [sys.executable, os.path.join(HOOKS, "devir_memory.py"), "upsert",
                 "--file", mem, "--key", key, "--line", line, "--max-lines", str(maxl)],
                capture_output=True, text=True)

        upsert("session-state-feature-login.md",
               "- [Session state: feature/login](session-state-feature-login.md) — resume point")
        body = open(mem).read()
        check("M1 yeni key append edildi", "session-state-feature-login.md" in body)
        check("M1b mevcut satır korundu", "existing.md" in body)
        n_before = body.count("session-state-feature-login.md")
        # aynı key tekrar (idempotent — duplicate YOK)
        upsert("session-state-feature-login.md",
               "- [Session state: feature/login](session-state-feature-login.md) — GÜNCEL")
        body = open(mem).read()
        check("M2 idempotent (duplicate satır yok)",
              body.count("session-state-feature-login.md") == n_before, str(body.count("session-state-feature-login.md")))
        check("M2b satır yerinde güncellendi (replace)", "GÜNCEL" in body)
        # multi-line reddi
        r = upsert("k", "satir1\nsatir2")
        check("M3 multi-line --line reddedildi", "tek satır" in r.stderr, r.stderr[:120])
        # exit 0 her zaman
        check("M3b multi-line yine exit 0", r.returncode == 0)

        # ================= L2 not precedence (scan) =================
        print("\n== L2 precedence (scan_notes) ==")
        opens = dc.scan_notes(repo, statuses=("open", "draft"))
        statuses = {n["fm"].get("status") for n in opens}
        check("scan_notes consumed'i hariç tutar", "consumed" not in statuses, str(statuses))
        check("scan_notes open+draft döndürür", "open" in statuses, str(statuses))

    finally:
        # cleanup: fake state dosyaları + .fired markerlar + temp repo
        for s in FAKE_SESSIONS:
            for suff in (".dump.md", ".fired"):
                p = os.path.join(STATE_DIR, s + suff)
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'='*48}\nSONUÇ: {len(PASS)} geçti, {len(FAIL)} kaldı")
    if FAIL:
        print("KALAN:", ", ".join(FAIL))
        sys.exit(1)
    print("✅ TÜM E2E TESTLER GEÇTİ")


if __name__ == "__main__":
    main()
