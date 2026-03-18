"""File and path utilities for the FMS pipeline."""
from __future__ import annotations

import os
import shutil
from typing import Generator


def ensure_dir(path: str) -> None:
    """Create directory (and parents) if it does not exist."""
    os.makedirs(path, exist_ok=True)


def copy_file(src: str, dst_dir: str) -> str:
    """
    Copy *src* into *dst_dir*, creating the destination directory if needed.

    Returns the full path of the copied file.
    """
    ensure_dir(dst_dir)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return dst


def copy_shapefile(src_base: str, dst_dir: str) -> list[str]:
    """
    Copy all sidecar files for a shapefile (.shp, .dbf, .shx, .prj, .cpg).

    Parameters
    ----------
    src_base : str
        Path to the .shp file (with or without extension).
    dst_dir : str
        Destination directory.

    Returns
    -------
    list[str]
        Paths of all files successfully copied.
    """
    base = src_base.removesuffix(".shp")
    extensions = (".shp", ".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx")
    copied: list[str] = []
    for ext in extensions:
        candidate = base + ext
        if os.path.isfile(candidate):
            copied.append(copy_file(candidate, dst_dir))
    return copied


def list_files(directory: str, extension: str) -> list[str]:
    """
    Return sorted absolute paths of files with *extension* in *directory*.

    Parameters
    ----------
    directory : str
        Directory to search (non-recursive).
    extension : str
        File extension including the dot, e.g. '.snp'.
    """
    if not os.path.isdir(directory):
        return []
    ext = extension.lower()
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(ext)
    )


def write_flag_file(directory: str, filename: str = "ready.flag") -> str:
    """
    Write an empty trigger/flag file to *directory*.

    Used by the surface packager to signal readiness to the mosaic publisher.

    Returns
    -------
    str
        Absolute path of the flag file.
    """
    ensure_dir(directory)
    flag_path = os.path.join(directory, filename)
    with open(flag_path, "w", encoding="utf-8") as fh:
        fh.write("")
    return flag_path


def safe_remove(path: str) -> None:
    """Remove a file if it exists; silently skip if it does not."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
