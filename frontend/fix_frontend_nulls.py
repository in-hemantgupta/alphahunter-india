from pathlib import Path

targets = list(Path("src").rglob("*.tsx"))

patterns = {
    ".total_score.toFixed(": ".total_score?.toFixed(",
    ".score.toFixed(": ".score?.toFixed(",
    ".weight.toFixed(": ".weight?.toFixed(",
    ".old_weight.toFixed(": ".old_weight?.toFixed(",
    ".new_weight.toFixed(": ".new_weight?.toFixed(",
    ".allocation.toFixed(": ".allocation?.toFixed(",
    ".returns_1y.toFixed(": ".returns_1y?.toFixed(",
    ".returns_6m.toFixed(": ".returns_6m?.toFixed(",
    ".volume_ratio.toFixed(": ".volume_ratio?.toFixed(",
    ".current_price.toFixed(": ".current_price?.toFixed(",
}

for file in targets:
    txt = file.read_text()

    original = txt

    for old,new in patterns.items():
        txt = txt.replace(old,new)

    # optional safer rendering
    txt = txt.replace("?.toFixed(1)}", "?.toFixed(1) || '0'}")
    txt = txt.replace("?.toFixed(2)}", "?.toFixed(2) || '0'}")
    txt = txt.replace("?.toFixed(0)}", "?.toFixed(0) || '0'}")

    if txt != original:
        file.write_text(txt)
        print("patched:", file)

print("done")
