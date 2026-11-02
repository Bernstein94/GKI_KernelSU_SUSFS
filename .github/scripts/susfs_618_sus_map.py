#!/usr/bin/env python3
"""Add the SUSFS SUS_MAP skip to show_smaps_rollup() on android17-6.18.

The 6.12 patch's hunk for this function does not survive the 6.18 move to
lock_ctx_mm()/VMA_ITERATOR (Google keeps reworking it per sublevel, so a
context patch rejects on some trees while applying with a 40-line offset on
others). Anchor on the loop shape instead of on line numbers:

    do {
            <maybe smap_gather_stats(...)>
            last_vma_end = vma->vm_end;

We insert the skip right after the opening `do {` and the label immediately
before the first `last_vma_end = vma->vm_end;`, so the vma still counts as
reported but contributes no stats. Tolerates any smap_gather_stats() arity or
whitespace, and fails loudly if the function or the loop cannot be found.

Usage: susfs_618_sus_map.py <kernel/common>
"""

import re
import sys
from typing import NoReturn


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


GUARD = """#ifdef CONFIG_KSU_SUSFS_SUS_MAP
\t\tif (vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))
\t\t\tgoto bypass_orig_flow;
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP
"""

LABEL = """#ifdef CONFIG_KSU_SUSFS_SUS_MAP
bypass_orig_flow:
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP
"""


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_618_sus_map.py <kernel/common>")
    path = f"{sys.argv[1].rstrip('/')}/fs/proc/task_mmu.c"
    src = open(path, encoding="utf-8").read()

    fn = src.find("static int show_smaps_rollup(")
    if fn < 0:
        die(f"{path}: show_smaps_rollup() not found")

    # Scope the idempotency check to this function: pagemap_read() also uses a
    # bypass_orig_flow label, so a file-wide grep would wrongly report done.
    nxt = src.find("\nstatic ", fn + 10)
    region = src[fn : nxt if nxt > 0 else len(src)]
    if "bypass_orig_flow" in region:
        print("  task_mmu.c: SUS_MAP skip already present in show_smaps_rollup()")
        return

    # find the loop inside the function
    loop = re.compile(r"(?m)^\tdo \{\n")
    m = loop.search(src, fn)
    if not m:
        die(f"{path}: `do {{` loop not found inside show_smaps_rollup()")
    body_start = m.end()

    tail = re.compile(r"(?m)^(?:[ \t]*)last_vma_end = vma->vm_end;\n")
    t = tail.search(src, body_start)
    if not t:
        die(f"{path}: `last_vma_end = vma->vm_end;` not found inside the loop")

    # insert the label before last_vma_end, the guard right after `do {`
    src = src[: t.start()] + LABEL + src[t.start() :]
    src = src[:body_start] + GUARD + src[body_start:]

    open(path, "w", encoding="utf-8").write(src)

    check = open(path, encoding="utf-8").read()
    for needle in ("goto bypass_orig_flow;", "bypass_orig_flow:"):
        if needle not in check:
            die(f"{path}: insertion failed (missing {needle!r})")
    print("  task_mmu.c: SUS_MAP skip inserted into show_smaps_rollup()")


if __name__ == "__main__":
    main()
