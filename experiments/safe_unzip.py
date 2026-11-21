"""Safe unzip of an untrusted archive: refuses absolute paths / '..' traversal / symlinks, reports sizes.
Usage: python -I safe_unzip.py <zip> <dest_dir> [password]"""
import os
import sys
import zipfile

zpath, dest = sys.argv[1], sys.argv[2]
pwd = sys.argv[3].encode() if len(sys.argv) > 3 else None
dest = os.path.abspath(dest)
os.makedirs(dest, exist_ok=True)
z = zipfile.ZipFile(zpath)
n = skipped = total = 0
for info in z.infolist():
    name = info.filename
    # Windows-encoded names (cp437 flag unset) -> try utf-8 then cp852
    if not (info.flag_bits & 0x800):
        try:
            name = name.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                name = name.encode("cp437").decode("cp852")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    target = os.path.abspath(os.path.join(dest, name))
    is_link = (info.external_attr >> 16) & 0o170000 == 0o120000
    if not target.startswith(dest + os.sep) or is_link:
        skipped += 1
        print("SKIP", repr(name))
        continue
    if name.endswith("/"):
        os.makedirs(target, exist_ok=True)
        continue
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with z.open(info, pwd=pwd) as src, open(target, "wb") as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)
    n += 1
    total += info.file_size
print(f"extracted {n} files, {total/1e6:.1f} MB, skipped {skipped}")
