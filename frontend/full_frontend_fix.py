from pathlib import Path
import re

tsx_files = list(Path("src").rglob("*.tsx"))

# ---------- direct replacements ----------
replacements = {
    # Dashboard unsafe toFixed
    "topStocks[0]?.total_score.toFixed(1)":
        "(topStocks[0]?.total_score ?? 0).toFixed(1)",

    "stock.total_score.toFixed(1)":
        "(stock.total_score ?? 0).toFixed(1)",

    "selectedStock.total_score.toFixed(1)":
        "(selectedStock.total_score ?? 0).toFixed(1)",

    "item.weight.toFixed(0)":
        "(item.weight ?? 0).toFixed(0)",

    "item.score.toFixed(1)":
        "(item.score ?? 0).toFixed(1)",

    # reduce
    "sum + s.total_score":
        "sum + (s.total_score ?? 0)",
}

# ---------- regex replacements ----------
regex_patterns = [
    # filters/comparisons
    (r"s\.total_score\s*>=\s*60", "(s.total_score ?? 0) >= 60"),
    (r"s\.total_score\s*>=\s*40", "(s.total_score ?? 0) >= 40"),
    (r"s\.total_score\s*>=\s*20", "(s.total_score ?? 0) >= 20"),
    (r"s\.total_score\s*<\s*80", "(s.total_score ?? 0) < 80"),
    (r"s\.total_score\s*<\s*60", "(s.total_score ?? 0) < 60"),
    (r"s\.total_score\s*<\s*40", "(s.total_score ?? 0) < 40"),
    (r"s\.total_score\s*<\s*20", "(s.total_score ?? 0) < 20"),
]

patched = []

for file in tsx_files:
    txt = file.read_text()
    original = txt

    # direct replace
    for old, new in replacements.items():
        txt = txt.replace(old, new)

    # regex replace
    for pattern, repl in regex_patterns:
        txt = re.sub(pattern, repl, txt)

    # patch interface Stock numeric fields -> nullable
    if "interface Stock" in txt:
        txt = re.sub(
            r"total_score:\s*number",
            "total_score?: number | null",
            txt
        )
        txt = re.sub(
            r"current_price:\s*number",
            "current_price?: number | null",
            txt
        )
        txt = re.sub(
            r"returns_1y:\s*number",
            "returns_1y?: number | null",
            txt
        )
        txt = re.sub(
            r"returns_6m:\s*number",
            "returns_6m?: number | null",
            txt
        )
        txt = re.sub(
            r"volume_ratio:\s*number",
            "volume_ratio?: number | null",
            txt
        )

    # generic unsafe .toFixed patterns (convert x.toFixed -> x?.toFixed)
    txt = re.sub(
        r'(?<!\?)([A-Za-z0-9_\.]+)\.toFixed\(',
        r'\1?.toFixed(',
        txt
    )

    if txt != original:
        file.write_text(txt)
        patched.append(str(file))

print("\nPATCHED FILES:")
for p in patched:
    print(" -", p)

print("\nDONE")
