import re

with open(r"E:\EEG_fNIRS_SparseRouting_Monochrome_Refined_Fixed.svg.bak", "r", encoding="utf-8") as f:
    text = f.read()

with open("scripts/target_elements_dump.txt", "w", encoding="utf-8") as out:
    out.write("--- TEXT NODES around 1650 and 2000 ---\n")
    for m in re.finditer(r'<text\s+([^>]*?)>(.*?)</text>', text, re.DOTALL):
        attrs = m.group(1)
        body = m.group(2)
        if any(k in attrs for k in ['x="165', 'x="166', 'x="164', 'x="200', 'x="199']):
            out.write(f"Attrs: {attrs} | Body: {body}\n")

    out.write("\n--- RECTS around 1650 and 2000 ---\n")
    for m in re.finditer(r'<rect\s+([^>]*?)>', text):
        attrs = m.group(1)
        if any(k in attrs for k in ['x="16', 'x="19', 'x="20']):
            out.write(f"Rect: {attrs}\n")

print("Dumped.")
