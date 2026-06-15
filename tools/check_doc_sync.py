#!/usr/bin/env python3
"""Diyagram/doküman senkron kontrolü — skill/hook değişince doc güncel kaldı mı?

Vendored hook'lardaki sayısal sabitleri, settings.example.json'daki hook event'lerini ve
skills/*/SKILL.md'deki skill adlarını çıkarır, docs/workflow.md'de geçtiklerini doğrular.
Drift varsa exit 1 + rapor.

KAPSAM: sabit-drift + hook-wiring drift + skill-adı drift (en sık kayan, en kolay otomatize
edilen kısımlar). Skill-adı drift'i: yeni bir skill eklenip (ör. `/devir-land`) workflow.md'ye
dokümante edilmezse yakalar — her skills/*/SKILL.md `name:`'i workflow.md'de geçmeli.
YAPISAL diyagram doğruluğu (yeni faz/akış/kutu) bu kontrolün DIŞINDA — onu insan günceller
(bkz. docs/diagrams/README.md §3). Yanlış-pozitif vermez: küçük tamsayılar (6/7 gibi) zaten
docs'ta başka yerde geçebilir; asıl güç 260_000 / 262_144 gibi ayırt edici sabitlerdedir.
Skill adları kelime-sınırıyla aranır → `devir`, `devir-notes` içine karışmaz.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, "hooks")
DOC = os.path.join(REPO, "docs", "workflow.md")
ARCH = os.path.join(REPO, "docs", "architecture.md")
SETTINGS = os.path.join(REPO, "settings.example.json")
SKILLS_GLOB = os.path.join(REPO, "skills", "*", "SKILL.md")
AGENTS_GLOB = os.path.join(REPO, "agents", "*.md")
WORKFLOWS_GLOB = os.path.join(REPO, "workflows", "*.js")

# (hook dosyası, sabit adı) — koddan int çıkarılır, doc'ta '{:_}' biçimi aranır.
CONST_SOURCES = [
    ("devir-autotrigger.py", "THRESHOLD"),
    ("devir-autotrigger.py", "REFIRE_GAP"),
    ("devir-autotrigger.py", "CLEANUP_DAYS"),
    ("devir-autotrigger.py", "NOTE_FRESH_HOURS"),
    ("devir-sessionstart.py", "INJECT_CAP"),
    ("devir_common.py", "DEFAULT_WINDOW"),
    ("devir_common.py", "WIDE_WINDOW"),
]


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_int(src, name):
    """`NAME = 123_456` (satır başı, opsiyonel yorum) → int. Bulunamazsa None."""
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*([\d_]+)", src, re.MULTILINE)
    return int(m.group(1).replace("_", "")) if m else None


def doc_has_number(doc, value):
    """value, doc'ta '260_000' VEYA '260000' biçiminde geçiyor mu?"""
    return f"{value:_}" in doc or str(value) in doc


def frontmatter_name(src):
    """YAML frontmatter'ın ilk `name:` değerini döndür (ilk --- bloğu). Bulunamazsa None."""
    m = re.search(r"^---\s*\n(.*?)\n---", src, re.DOTALL)
    block = m.group(1) if m else src
    nm = re.search(r"^name:\s*(.+?)\s*$", block, re.MULTILINE)
    return nm.group(1).strip() if nm else None


def doc_has_skill(doc, name):
    """name, doc'ta kelime-sınırıyla (opsiyonel '/' önekli) geçiyor mu?

    Tire token'ın parçası sayılır → `devir`, `devir-notes`/`devir-land` içine karışmaz;
    her skill kendi tam adıyla aranır.
    """
    return re.search(rf"(?<![\w-])/?{re.escape(name)}(?![\w-])", doc) is not None


def main():
    problems = []
    notes = []

    for f in [DOC, ARCH, SETTINGS] + [os.path.join(HOOKS, fn) for fn, _ in CONST_SOURCES]:
        if not os.path.isfile(f):
            problems.append(f"KAYIP DOSYA: {f}")
    if problems:
        print("\n".join("✗ " + p for p in problems))
        return 1

    doc = read(DOC)
    docset = doc + "\n" + read(ARCH)   # skill adları workflow.md VEYA architecture.md'de geçebilir

    # 1) sabitler
    src_cache = {}
    for fn, name in CONST_SOURCES:
        src = src_cache.setdefault(fn, read(os.path.join(HOOKS, fn)))
        val = extract_int(src, name)
        if val is None:
            problems.append(f"{fn}: `{name}` sabiti koddan çıkarılamadı (yeniden adlandırıldı?).")
            continue
        if doc_has_number(doc, val):
            notes.append(f"✓ {name} = {val:_}  (workflow.md'de mevcut)")
        else:
            problems.append(
                f"DRIFT: {fn}:{name} = {val:_} kodda var ama workflow.md'de YOK. "
                f"§8 sabitler tablosunu güncelle."
            )

    # 2) --max-lines default (argparse)
    mem = read(os.path.join(HOOKS, "devir_memory.py")) if os.path.isfile(
        os.path.join(HOOKS, "devir_memory.py")) else ""
    m = re.search(r'--max-lines"[^)]*default\s*=\s*(\d+)', mem)
    if m:
        v = int(m.group(1))
        (notes if doc_has_number(doc, v) else problems).append(
            f"✓ --max-lines default = {v}  (workflow.md'de mevcut)" if doc_has_number(doc, v)
            else f"DRIFT: --max-lines default={v} kodda var ama workflow.md'de YOK."
        )

    # 3) hook event wiring
    try:
        events = list(json.loads(read(SETTINGS)).get("hooks", {}).keys())
    except Exception as e:
        problems.append(f"settings.example.json parse hatası: {e}")
        events = []
    for ev in events:
        if ev in doc:
            notes.append(f"✓ hook event `{ev}` workflow.md'de geçiyor")
        else:
            problems.append(f"DRIFT: settings.example.json'da `{ev}` event'i var ama workflow.md'de YOK.")

    # 4) skill-adı drift — her skills/*/SKILL.md `name:`'i workflow.md VEYA architecture.md'de geçmeli
    skill_files = sorted(glob.glob(SKILLS_GLOB))
    if not skill_files:
        problems.append(f"KAYIP: {os.path.relpath(SKILLS_GLOB, REPO)} hiç eşleşmedi (skills/ taşındı mı?).")
    for sf in skill_files:
        rel = os.path.relpath(sf, REPO)
        name = frontmatter_name(read(sf))
        if not name:
            problems.append(f"{rel}: frontmatter `name:` okunamadı.")
        elif doc_has_skill(docset, name):
            notes.append(f"✓ skill `/{name}` workflow.md/architecture.md'de belgeli")
        else:
            problems.append(
                f"DRIFT: skill `/{name}` ({rel}) var ama workflow.md/architecture.md'de geçmiyor — "
                f"tetik tablosu/§7 + diyagramlara ya da architecture.md'ye ekle."
            )

    # 5) agent-wiring drift — workflows/*.js'in andığı her `agentType` için agents/<ad>.md olmalı
    agent_names = {}  # name -> rel path
    for af in sorted(glob.glob(AGENTS_GLOB)):
        nm = frontmatter_name(read(af))
        if not nm:
            problems.append(f"{os.path.relpath(af, REPO)}: frontmatter `name:` okunamadı.")
            continue
        agent_names[nm] = os.path.relpath(af, REPO)
        if nm != os.path.splitext(os.path.basename(af))[0]:
            notes.append(f"⚠ agent `{nm}` dosya adı ({os.path.basename(af)}) ile eşleşmiyor (advisory).")
    wf_files = sorted(glob.glob(WORKFLOWS_GLOB))
    referenced = set()
    for wf in wf_files:
        for m in re.finditer(r"agentType:\s*['\"]([\w-]+)['\"]", read(wf)):
            referenced.add((m.group(1), os.path.relpath(wf, REPO)))
    for ref, wfrel in sorted(referenced):
        if ref in agent_names:
            notes.append(f"✓ agentType `{ref}` ({wfrel}) → {agent_names[ref]}")
        else:
            problems.append(
                f"DRIFT: workflow `{wfrel}` `agentType: {ref}` kullanıyor ama agents/{ref}.md YOK — "
                f"agent prompt'unu ekle ya da agentType'ı düzelt."
            )

    print("\n".join(notes))
    if problems:
        print("\n" + "\n".join("✗ " + p for p in problems))
        print(f"\n✗ DRIFT: {len(problems)} sorun. Diyagram/doc güncellenmeli (bkz. docs/diagrams/README.md).")
        return 1
    print(f"\n✅ Senkron: {len(notes)} kontrol geçti, drift yok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
