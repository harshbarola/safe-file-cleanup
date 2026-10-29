
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import sys


QUARANTINE_NAME = ".cleanup_quarantine"


def calculate_hash(path):
    digest = hashlib.sha256()

    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        print(f"Could not read {path}: {error}")
        return None


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024


def is_inside(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def scan_folder(folder, min_size_mb):
    quarantine_root = folder / QUARANTINE_NAME
    file_hashes = {}
    large_files = []
    total_size = 0
    total_files = 0
    threshold = min_size_mb * 1024 * 1024

    print(f"\nScanning: {folder}\n")

    for path in folder.rglob("*"):
        if is_inside(path, quarantine_root) or not path.is_file():
            continue

        try:
            size = path.stat().st_size
        except OSError as error:
            print(f"Could not access {path}: {error}")
            continue

        total_files += 1
        total_size += size

        if size > threshold:
            large_files.append((path, size))

        fingerprint = calculate_hash(path)

        if fingerprint is not None:
            file_hashes.setdefault(fingerprint, []).append({
                "path": path,
                "size": size
            })

    duplicate_groups = [
        group for group in file_hashes.values() if len(group) > 1
    ]

    proposed = []

    for group in duplicate_groups:
        # Keep one copy; propose the remaining identical files.
        proposed.extend(group[1:])

    large_files.sort(key=lambda item: item[1], reverse=True)

    print("--- SCAN SUMMARY ---")
    print(f"Files scanned: {total_files}")
    print(f"Total size: {format_size(total_size)}")

    print(f"\n--- FILES LARGER THAN {min_size_mb:g} MB ---")

    if large_files:
        print(f"{'File Name':<30} {'Size':>12}")
        print("-" * 44)
        for path, size in large_files:
            print(f"{path.name:<30} {format_size(size):>12}")
            print(f"  {path.resolve()}")
    else:
        print("No large files found.")

    print("\n--- CLEANUP PREVIEW ---")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Proposed files to quarantine: {len(proposed)}")
    print(
        "Potential space recovered: "
        + format_size(sum(item["size"] for item in proposed))
    )

    if proposed:
        print("\nProposed files:")
        for item in proposed:
            print(f"  {item['path']} ({format_size(item['size'])})")

    print("\nDry run: no files have been changed.")
    return proposed


def create_session(quarantine_root):
    quarantine_root.mkdir(parents=True, exist_ok=True)
    number = 1

    while True:
        session = quarantine_root / f"session_{number:03d}"
        try:
            session.mkdir()
            return session
        except FileExistsError:
            number += 1


def unique_destination(files_dir, filename):
    original = Path(filename)
    candidate = files_dir / filename
    number = 1

    while candidate.exists():
        candidate = files_dir / (
            f"{original.stem}_{number}{original.suffix}"
        )
        number += 1

    return candidate


def save_manifest(manifest_path, manifest):
    temporary = manifest_path.with_name("manifest.tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)

    temporary.replace(manifest_path)


def quarantine_files(folder, proposed):
    if not proposed:
        print("No duplicate files to quarantine.")
        return

    print("\nFiles selected for quarantine:")
    for item in proposed:
        print(f"  {item['path']} ({format_size(item['size'])})")

    answer = input(
        "\nType QUARANTINE to move these files: "
    ).strip()

    if answer != "QUARANTINE":
        print("Cancelled. No files were moved.")
        return

    session = create_session(folder / QUARANTINE_NAME)
    files_dir = session / "files"
    files_dir.mkdir()

    manifest_path = session / "manifest.json"
    manifest = {
        "session": session.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "files": []
    }

    for item in proposed:
        path = item["path"]
        fingerprint = calculate_hash(path)

        manifest["files"].append({
            "original_path": str(path.resolve()),
            "quarantine_path": None,
            "size_bytes": item["size"],
            "sha256": fingerprint,
            "status": "pending",
            "error": None
        })

    save_manifest(manifest_path, manifest)

    for record in manifest["files"]:
        source = Path(record["original_path"])

        try:
            if not source.is_file():
                raise FileNotFoundError("Source file no longer exists.")

            current_hash = calculate_hash(source)

            if current_hash is None or current_hash != record["sha256"]:
                raise OSError("File changed since the scan.")

            destination = unique_destination(files_dir, source.name)

            # Exclusive creation prevents overwriting an existing target.
            with destination.open("xb"):
                pass

            try:
                shutil.move(str(source), str(destination))
            except Exception:
                destination.unlink(missing_ok=True)
                raise

            record["quarantine_path"] = str(destination.resolve())
            record["status"] = "moved"

        except (OSError, shutil.Error) as error:
            record["status"] = "error"
            record["error"] = str(error)
            print(f"Could not quarantine {source}: {error}")

        try:
            save_manifest(manifest_path, manifest)
        except OSError as error:
            print(f"WARNING: Manifest update failed: {error}")
            print("Stop and inspect the session before continuing.")
            return

    manifest["status"] = (
        "completed"
        if all(record["status"] == "moved" for record in manifest["files"])
        else "completed_with_errors"
    )
    save_manifest(manifest_path, manifest)

    moved = sum(record["status"] == "moved" for record in manifest["files"])

    print("\n--- QUARANTINE SUMMARY ---")
    print(f"Files moved: {moved}")
    print(f"Session: {session}")
    print(f"Manifest: {manifest_path}")


def restore_session(session_id, quarantine_root=None):
    if (
        not session_id
        or Path(session_id).name != session_id
        or session_id in {".", ".."}
    ):
        print("Error: Invalid session ID.")
        return

    if quarantine_root is None:
        quarantine_root = Path.cwd() / QUARANTINE_NAME

    quarantine_root = Path(quarantine_root).resolve()
    session = quarantine_root / session_id
    manifest_path = session / "manifest.json"
    files_dir = (session / "files").resolve()

    if not session.is_dir() or not manifest_path.is_file():
        print("Error: Session or manifest not found.")
        return

    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read manifest: {error}")
        return

    if not isinstance(manifest.get("files"), list):
        print("Error: Invalid manifest format.")
        return

    restored = 0
    skipped = 0

    for record in manifest["files"]:
        if not isinstance(record, dict) or record.get("status") != "moved":
            continue

        try:
            original_value = record.get("original_path")
            quarantine_value = record.get("quarantine_path")

            if not original_value or not quarantine_value:
                raise ValueError("Missing path information.")

            original = Path(original_value)
            quarantined = Path(quarantine_value).resolve()

            if not is_inside(quarantined, files_dir):
                raise ValueError("Quarantine path is outside the session.")

            if not quarantined.is_file():
                raise FileNotFoundError(
                    f"Quarantined file is missing: {quarantined}"
                )

            if original.exists():
                print(f"RESTORE CONFLICT: {original}")
                print("Resolve the conflict manually; file left untouched.")
                skipped += 1
                continue

            if calculate_hash(quarantined) != record.get("sha256"):
                raise OSError("Quarantined file failed hash verification.")

            # Recheck immediately before moving. Never intentionally overwrite.
            if original.exists():
                print(f"RESTORE CONFLICT: {original}")
                skipped += 1
                continue

            original.parent.mkdir(parents=True, exist_ok=True)

            # Create the destination exclusively to avoid overwriting files.
            with original.open("xb"):
                pass

            try:
                shutil.move(str(quarantined), str(original))
            except Exception:
                original.unlink(missing_ok=True)
                raise

            record["status"] = "restored"
            record["restored_at"] = datetime.now(timezone.utc).isoformat()
            restored += 1
            print(f"Restored: {original}")

        except (OSError, ValueError, shutil.Error) as error:
            record["error"] = str(error)
            skipped += 1
            print(f"Restore failed: {error}")

        try:
            save_manifest(manifest_path, manifest)
        except OSError as error:
            print(f"WARNING: Could not save manifest: {error}")
            print("Inspect file locations before attempting another restore.")
            return

    manifest["status"] = (
        "restored"
        if all(record.get("status") == "restored"
               for record in manifest["files"])
        else "restore_incomplete"
    )

    save_manifest(manifest_path, manifest)

    print("\n--- RESTORE SUMMARY ---")
    print(f"Files restored: {restored}")
    print(f"Files skipped or failed: {skipped}")


def main():
    parser = argparse.ArgumentParser(
        description="Scan files and safely preview duplicate cleanup."
    )
    parser.add_argument("folder", help="Folder path to scan")
    parser.add_argument(
        "--min-size",
        type=float,
        default=100,
        help="Large-file threshold in MB (default: 100)"
    )
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help="Quarantine duplicates after confirmation"
    )

    args = parser.parse_args()

    if args.min_size < 0:
        parser.error("--min-size cannot be negative")

    folder = Path(args.folder).expanduser()

    if not folder.is_dir():
        parser.error("Please provide an existing folder.")

    folder = folder.resolve()
    proposed = scan_folder(folder, args.min_size)

    if args.quarantine:
        quarantine_files(folder, proposed)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) != 3:
            print("Usage: python cleanup.py restore SESSION_ID")
            sys.exit(1)

        restore_session(sys.argv[2])
    else:
        main()
