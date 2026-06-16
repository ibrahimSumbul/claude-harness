"""devir hook'ları için ortak yardımcılar (v2).

Bütün fonksiyonlar defensive: hata olursa sessizce güvenli default döner.
Bir hook compaction'ı veya prompt'u ASLA kıramaz — her şey try/except içinde.

Kullanım: devir-autotrigger.py + devir-precompact.py + devir-sessionstart.py bunu import eder
(script kendi dizinini sys.path'e ekler → `import devir_common` çözülür).
Mimari/karar gerekçeleri: ~/.claude/skills/devir/DESIGN.md
"""
import json
import os
import re
import secrets
import subprocess
from datetime import datetime

DEFAULT_WINDOW = 262_144          # transcript kuyruğundan okunacak byte (256 KB)
WIDE_WINDOW = 1_048_576           # usage bulunamazsa genişlet (1 MB)
BYTES_PER_TOKEN_FALLBACK = 4      # usage hiç yoksa kaba tahmin: boyut / 4

CONFIG_PATH = os.path.expanduser("~/.claude/devir.config.json")
STATE_DIR = os.path.expanduser("~/.claude/.devir-state")

# Not statü önceliği (resume precedence; superseded/consumed listeden düşer)
STATUS_RANK = {"draft": 0, "open": 1, "consumed": 2, "superseded": -1}

DEFAULT_REDACT_PATTERNS = [
    # env/key-value secrets: api_key, secret_key, access_key, client_secret, token, password...
    r"(?i)([a-z0-9_]*(?:api[_-]?key|secret[_-]?key|access[_-]?key|client[_-]?secret|token|secret|password|passwd))\s*[:=]\s*['\"]?[^'\"\s`]+",
    r"(?i)bearer\s+[a-z0-9._-]+",
    # provider token prefixes (github classic/fine-grained, slack, supabase, gitlab, stripe)
    r"\b(sk|ghp|gho|ghu|ghs|ghr|github_pat|xox[baprs]|sbp|glpat)[-_][a-zA-Z0-9._-]{12,}\b",
    r"\bAKIA[0-9A-Z]{16}\b",                        # AWS access key id
    r"\bAIza[0-9A-Za-z_-]{30,}",                    # Google API key (toleranslı uzunluk)
    r"\beyJ[a-zA-Z0-9._-]{20,}\b",                  # JWT
    r"://[^/\s:@]+:[^/\s@]+@",                       # creds embedded in URL: scheme://user:pass@
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",    # PEM private key block
]


# ---------------------------------------------------------------- config
def load_config():
    """~/.claude/devir.config.json — opsiyonel. Yoksa güvenli default.
    capture_raw_messages default FALSE (gizlilik); redaction patterns default set."""
    cfg = {
        "capture_raw_messages": False,
        "redact_patterns": list(DEFAULT_REDACT_PATTERNS),
    }
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                if isinstance(user.get("capture_raw_messages"), bool):
                    cfg["capture_raw_messages"] = user["capture_raw_messages"]
                if isinstance(user.get("redact_patterns"), list):
                    pats = [p for p in user["redact_patterns"] if isinstance(p, str) and p.strip()]
                    if pats:
                        cfg["redact_patterns"] = pats
    except Exception:
        pass
    return cfg


# ---------------------------------------------------------------- git
def git(args, cwd):
    """git komutunu cwd'de çalıştır, stdout'u strip'le döndür; hata → ''."""
    try:
        out = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def repo_root(cwd):
    return git(["rev-parse", "--show-toplevel"], cwd) or ""


def main_worktree_root(cwd):
    """Ana (birincil) worktree kökü — paylaşılan + KALICI. Linked worktree İÇİNDEN
    çağrılsa bile ana checkout'u verir; böylece L2 notlar (gitignored, commit edilmez)
    worktree prune'unda KAYBOLMAZ ve tüm worktree'ler tek not dizinini görür.
    `--git-common-dir` ana repo'nun .git'ini döndürür (linked worktree'de bile); ebeveyni =
    ana worktree kökü. Çözülemezse repo_root'a (mevcut worktree) düş — güvenli degrade."""
    common = git(["rev-parse", "--git-common-dir"], cwd)
    if not common:
        return repo_root(cwd)
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    parent = os.path.dirname(os.path.normpath(common))
    return parent or repo_root(cwd)


# ---------------------------------------------------------------- notes (L2)
def slugify(text):
    if not text:
        return "unknown"
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(text)).strip("-").lower()
    return s or "unknown"


def notes_dir(cwd):
    """<ana-worktree>/.claude/docs/devir-notes — paylaşılan + KALICI. Repo yoksa ''.
    `main_worktree_root` ile çapalanır: linked worktree'de bile ana checkout'a yazılır →
    worktree prune'unda not kaybolmaz; tüm worktree'ler aynı dizini görür (cross-worktree resume)."""
    root = main_worktree_root(cwd)
    if not root:
        return ""
    return os.path.join(root, ".claude", "docs", "devir-notes")


def notes_archive_dir(cwd):
    nd = notes_dir(cwd)
    return os.path.join(nd, "archive") if nd else ""


def gen_note_id(branch):
    """<YYYY-MM-DD>-<branch-slug>-<rand6>. rand: secrets (hook'larda serbest)."""
    try:
        date = datetime.now().strftime("%Y-%m-%d")
    except Exception:
        date = "0000-00-00"
    return f"{date}-{slugify(branch)}-{secrets.token_hex(3)}"


def parse_frontmatter(text):
    """--- ... --- arası 'key: value' satırlarını dict olarak döndür."""
    fm = {}
    if not text or not text.startswith("---"):
        return fm
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def read_note(path):
    """(frontmatter dict, body str). Hata → ({}, '')."""
    try:
        with open(path, "r", errors="ignore") as f:
            text = f.read()
    except Exception:
        return {}, ""
    return parse_frontmatter(text), text


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except Exception:
        return 0


def scan_notes(cwd, statuses=("open", "draft")):
    """notes_dir'deki (archive hariç) notları frontmatter ile döndür.
    Liste: [{path, fm, mtime}], mtime DESC. statuses filtresi uygulanır."""
    nd = notes_dir(cwd)
    if not nd or not os.path.isdir(nd):
        return []
    out = []
    try:
        for name in os.listdir(nd):
            if not name.endswith(".md"):
                continue
            p = os.path.join(nd, name)
            if not os.path.isfile(p):  # archive/ alt-dizini atlanır
                continue
            fm, _ = read_note(p)
            st = (fm.get("status") or "").lower()
            if statuses and st not in statuses:
                continue
            out.append({"path": p, "fm": fm, "mtime": _mtime(p)})
    except Exception:
        return []
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def under_worktree(cwd, worktree):
    """cwd, worktree altında mı? Symlink farklarına (/var ↔ /private/var) karşı realpath-normalize."""
    if not worktree:
        return False
    try:
        c = os.path.realpath(cwd)
        w = os.path.realpath(worktree)
        return c == w or c.startswith(w.rstrip("/") + "/")
    except Exception:
        try:
            return cwd == worktree or cwd.startswith(worktree.rstrip("/") + "/")
        except Exception:
            return False


def redact_text(text, patterns):
    if not text:
        return text
    out = text
    for pat in (patterns or []):
        try:
            out = re.sub(pat, "[REDACTED]", out, flags=re.IGNORECASE)
        except Exception:
            continue
    return out


# ---------------------------------------------------------------- transcript
def _read_tail_bytes(path, max_bytes):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        return f.read()


def tail_lines(path, max_bytes=DEFAULT_WINDOW):
    """Kuyruktaki satırlar. İlk satır kısmi olabilir — JSON-parse edilemezse atlanır."""
    try:
        raw = _read_tail_bytes(path, max_bytes)
    except Exception:
        return []
    return raw.decode("utf-8", errors="ignore").splitlines()


def _usage_from_obj(obj):
    u = (obj.get("message") or {}).get("usage") or obj.get("usage") or {}
    if not u:
        return 0
    return (u.get("input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0))


def latest_usage_tokens(path):
    """Fiili context boyutu = transcript'teki EN GÜNCEL (son) usage (input + cache).
    Son usage-taşıyan satırı alır (max DEĞİL) → compaction sonrası eski yüksek değerle
    mis-fire/şişme olmaz. Hiç usage yoksa pencereyi genişlet, o da yoksa boyut/4."""
    for window in (DEFAULT_WINDOW, WIDE_WINDOW):
        latest = 0
        found = False
        for line in tail_lines(path, window):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = _usage_from_obj(obj)
            if t:
                latest = t      # son kazanır (sıra korunur)
                found = True
        if found:
            return latest
    try:
        return os.path.getsize(path) // BYTES_PER_TOKEN_FALLBACK
    except Exception:
        return 0


def _text_from_content(content):
    """message.content (str veya blok listesi) → düz metin. tool_result atlanır."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") in (None, "text") and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return " ".join(parts).strip()


def last_messages(path, max_bytes=DEFAULT_WINDOW, cap=400, redact_patterns=None):
    """Kuyruktan son gerçek user prompt'u + son assistant metnini best-effort çıkar."""
    last_user = ""
    last_assistant = ""
    for line in tail_lines(path, max_bytes):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        typ = obj.get("type")
        msg = obj.get("message") or {}
        if typ == "user":
            content = msg.get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            txt = _text_from_content(content)
            if txt:
                last_user = txt
        elif typ == "assistant":
            txt = _text_from_content(msg.get("content"))
            if txt:
                last_assistant = txt
    # Boundary-straddling secret sızmasın: TAM metni cap'ten ÖNCE redact et.
    if redact_patterns:
        last_user = redact_text(last_user, redact_patterns)
        last_assistant = redact_text(last_assistant, redact_patterns)
    return (last_user[:cap].strip(), last_assistant[:cap].strip())


def touched_files_from_transcript(path, max_bytes=WIDE_WINDOW, cap=25):
    """Tool-input'lardan dokunulan dosya yollarını mekanik çıkar (who96 pattern).
    assistant tool_use bloklarındaki input.file_path / path / notebook_path."""
    seen = []
    keys = ("file_path", "path", "notebook_path")
    for line in tail_lines(path, max_bytes):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "assistant":
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            inp = block.get("input")
            if not isinstance(inp, dict):
                continue
            for k in keys:
                v = inp.get(k)
                if isinstance(v, str) and v.strip() and v not in seen:
                    seen.append(v.strip())
    return seen[:cap]
