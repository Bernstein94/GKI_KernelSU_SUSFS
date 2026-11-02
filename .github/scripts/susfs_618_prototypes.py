#!/usr/bin/env python3
"""Add the prototypes fs/susfs.c is missing, for android17-6.18.

6.18's build enables -Wmissing-prototypes by default, and the 6.12 SUSFS source
only declares 19 of its ~40 non-static functions in include/linux/susfs.h (the
rest are defined in susfs.c with nothing declaring them). On 6.12 the warning
does not fire, so the same file compiles there and dies here:

  fs/susfs.c:1034:6: error: no previous prototype for function
                    'susfs_spoof_cmdline_or_bootconfig'
  fs/susfs.c:118:5:  error: no previous prototype for function
                    'susfs_add_sus_avd_allowed_by_type'
  ... (about 40 of them)

This scans the file for non-static definitions and inserts a prototype for any
that the file or its headers do not already declare, right after the last
#include. Signatures are copied verbatim from the definitions, so they cannot
drift from the implementation.

Idempotent, no-op when everything is already declared.

Usage: susfs_618_prototypes.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn

MARKER = "/* 6.18: prototypes for non-static susfs functions (added by GKI_KernelSU_SUSFS) */"

SKIP_NAMES = {"if", "for", "while", "switch", "return", "sizeof", "typeof", "container_of"}
DEF_RE = re.compile(r"^([A-Za-z_][\w \t\*]*?)\b([A-Za-z_]\w*)\s*\(")


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def collect_definitions(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (index, name, signature) for non-static definitions at column 0."""
    out = []
    for i, ln in enumerate(lines):
        if not ln or ln[0] in " \t/#*}" or ln.startswith("static") or ln.startswith("inline"):
            continue
        if "(" not in ln:
            continue
        m = DEF_RE.match(ln)
        if not m:
            continue
        name = m.group(2)
        if name in SKIP_NAMES:
            continue
        sig, depth, j = ln, ln.count("(") - ln.count(")"), i
        while depth > 0 and j + 1 < len(lines):
            j += 1
            sig += "\n" + lines[j]
            depth += lines[j].count("(") - lines[j].count(")")
        sig = sig.split("{")[0].rstrip()
        if ")" not in sig:
            continue
        sig = sig[: sig.rindex(")") + 1]
        if sig.count("(") != sig.count(")"):
            continue
        out.append((i, name, sig))
    return out


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_618_prototypes.py <kernel/common>")
    path = os.path.join(sys.argv[1].rstrip("/"), "fs/susfs.c")
    if not os.path.exists(path):
        die(f"{path}: not found")
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("  fs/susfs.c: prototypes already added")
        return

    lines = src.split("\n")
    defs = collect_definitions(lines)
    missing = [sig for _, name, sig in defs
               if not re.search(rf"\b{re.escape(name)}\s*\([^;]*\)\s*;", src)]

    if not missing:
        print("  fs/susfs.c: every non-static definition is already declared")
        return

    block = [MARKER] + [f"{sig};" for sig in missing] + [""]
    idx = [i for i, ln in enumerate(lines) if ln.startswith("#include")]
    if not idx:
        die("fs/susfs.c: no #include lines found")
    at = idx[-1] + 1
    lines[at:at] = [""] + block
    src = "\n".join(lines)
    open(path, "w", encoding="utf-8").write(src)
    print(f"  fs/susfs.c: added {len(missing)} prototype(s) after the last #include")

    check = open(path, encoding="utf-8").read()
    still = [n for _, n, _ in collect_definitions(check.split("\n"))
             if not re.search(rf"\b{re.escape(n)}\s*\([^;]*\)\s*;", check)]
    if still:
        die(f"fs/susfs.c: still undeclared after write: {', '.join(sorted(set(still))[:5])}")
    print("  fs/susfs.c: verified")


if __name__ == "__main__":
    main()
