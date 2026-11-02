#!/usr/bin/env python3
"""Silence -Wmissing-prototypes for the vendored fs/susfs.c on android17-6.18.

6.18 enables -Wmissing-prototypes by default and the 6.12 SUSFS source declares
only 19 of its ~40 non-static functions, so fs/susfs.c fails with ~40 of:

  fs/susfs.c:1034:6: error: no previous prototype for function
                    'susfs_spoof_cmdline_or_bootconfig'

Generating the missing prototypes was tried and is not safe: several functions
are defined twice under #if/#else with *different* signatures, e.g.

  #if LINUX_VERSION_CODE < KERNEL_VERSION(6,12,0)
  bool susfs_is_inode_sus_path(struct mnt_idmap* idmap, struct inode *inode)
  #else
  bool susfs_is_inode_sus_path(struct inode *inode)
  #endif

so a single emitted prototype collides with the other branch ("conflicting types
for 'susfs_is_inode_sus_path'"), and attribute-prefixed definitions
(__attribute__((hot)) bool susfs_is_inode_sus_kstat(...)) are easy to miss.

Since this is vendored third-party code whose definitions are the source of
truth, the pragmatic fix is to suppress that single warning for this one file.
Everything else keeps -Wmissing-prototypes.

Idempotent.

Usage: susfs_618_prototypes.py <kernel/common>
"""

import os
import sys

MARKER = "/* 6.18: silence -Wmissing-prototypes for this vendored file (GKI_KernelSU_SUSFS) */"

BLOCK = f"""{MARKER}
/*
 * 6.18 turns -Wmissing-prototypes on by default. The 6.12 SUSFS source only
 * declares 19 of its ~40 non-static functions, and several are defined twice
 * under #if/#else with different signatures (susfs_is_inode_sus_path), so
 * generated prototypes cannot cover them safely. The definitions stay the
 * source of truth; the warning is suppressed for this file only.
 */
#if defined(__clang__)
#pragma clang diagnostic ignored "-Wmissing-prototypes"
#elif defined(__GNUC__) && __GNUC__ >= 8
#pragma GCC diagnostic ignored "-Wmissing-prototypes"
#endif
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: susfs_618_prototypes.py <kernel/common>")
    path = os.path.join(sys.argv[1].rstrip("/"), "fs/susfs.c")
    if not os.path.exists(path):
        sys.exit(f"ERROR: {path}: not found")

    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("  fs/susfs.c: -Wmissing-prototypes already silenced")
        return

    lines = src.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith("#include")]
    if not idx:
        sys.exit("ERROR: fs/susfs.c: no #include lines found")
    at = idx[-1] + 1
    lines[at:at] = [""] + BLOCK.split("\n")
    open(path, "w", encoding="utf-8").write("\n".join(lines))

    check = open(path, encoding="utf-8").read()
    if MARKER not in check or "Wmissing-prototypes" not in check:
        sys.exit("ERROR: fs/susfs.c: pragma block missing after write")
    print("  fs/susfs.c: -Wmissing-prototypes silenced (vendored SUSFS source)")


if __name__ == "__main__":
    main()
