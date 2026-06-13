#!/usr/bin/env python3
"""devir — MEMORY.md index'ine çakışmasız (lock-guarded, atomik, idempotent) upsert.

NİYE: MEMORY.md tek paylaşımlı dosya, git-dışı, makine-local. Paralel session'lar aynı anda
append ederse last-writer-wins → satır kaybı. Bu helper read-modify-write'ı `flock` ile
serialize eder (lost-update yok) + temp-file `os.replace` ile atomik yazar (torn-file yok) +
key-bazlı idempotent upsert yapar (re-run / paralel duplicate üretmez).

/devir skill Faz 3'te ELLE Edit yerine bunu çağırır:
  python3 devir_memory.py upsert --file <MEMORY.md> --key <uniq-token> --line "<satır>"

Davranış: <file>'da `key` substring'ini içeren İLK satırı `line` ile değiştirir; yoksa sona ekler.
--max-lines aşılırsa stderr'e uyarı basar (SESSİZCE TRUNCATE ETMEZ). Her durumda exit 0
(best-effort; skill'i kırma). Hatalar stderr'e, exit yine 0.
"""
import argparse
import os
import sys
import tempfile

try:
    import fcntl
    _HAVE_FLOCK = True
except Exception:
    _HAVE_FLOCK = False


def _atomic_write(path, text):
    """Aynı dizinde temp dosyaya yaz, fsync, os.replace (atomik)."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".devir-mem-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def upsert(file_path, key, line, max_lines):
    if not key or not line:
        print("devir_memory: --key ve --line zorunlu", file=sys.stderr)
        return
    if "\n" in line or "\r" in line:
        # çok satırlı girdi idempotency'yi bozar (key tek satır eşler) → reddet
        print("devir_memory: --line tek satır olmalı (newline reddedildi)", file=sys.stderr)
        return
    d = os.path.dirname(os.path.abspath(file_path)) or "."
    os.makedirs(d, exist_ok=True)
    lock_path = os.path.join(d, ".devir-memory.lock")

    lock_f = None
    try:
        if _HAVE_FLOCK:
            lock_f = open(lock_path, "w")
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        else:
            print("devir_memory: UYARI — fcntl yok; eşzamanlılık koruması devre dışı (lost-update riski).",
                  file=sys.stderr)

        # read-modify-write (lock altında)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except FileNotFoundError:
            content = ""
        except Exception as e:
            print(f"devir_memory: okuma hatası: {e}", file=sys.stderr)
            return

        had_trailing_nl = content.endswith("\n") or content == ""
        lines = content.splitlines()

        replaced = False
        for i, ln in enumerate(lines):
            if key in ln:
                if lines[i] != line:
                    lines[i] = line
                replaced = True
                break
        if not replaced:
            lines.append(line)

        if max_lines and len(lines) > max_lines:
            print(
                f"devir_memory: UYARI — index {len(lines)} satır (>{max_lines}). "
                "Retention'ı topic dosyalarında gevşet; index'i kısalt.",
                file=sys.stderr,
            )

        new_content = "\n".join(lines)
        if had_trailing_nl or new_content:
            new_content += "\n"

        _atomic_write(file_path, new_content)
        action = "replaced" if replaced else "appended"
        print(f"devir_memory: {action} ({len(lines)} satır)")
    except Exception as e:
        print(f"devir_memory: hata: {e}", file=sys.stderr)
    finally:
        try:
            if lock_f is not None:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
                lock_f.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(prog="devir_memory")
    sub = ap.add_subparsers(dest="cmd")
    up = sub.add_parser("upsert", help="key-bazlı idempotent satır upsert")
    up.add_argument("--file", required=True)
    up.add_argument("--key", required=True)
    up.add_argument("--line", required=True)
    up.add_argument("--max-lines", type=int, default=200)
    try:
        args = ap.parse_args()
    except SystemExit:
        return  # exit 0 (best-effort)
    if args.cmd == "upsert":
        upsert(args.file, args.key, args.line, args.max_lines)


if __name__ == "__main__":
    main()
