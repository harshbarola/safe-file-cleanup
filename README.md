
# Safe File Cleanup

Safe File Cleanup is a Python-based command-line tool designed to scan directories, identify duplicate files, and discover large files that consume unnecessary storage space.

The tool uses SHA-256 hashing to detect files with identical contents, generates cleanup previews before making changes, and moves selected duplicate files into a dedicated quarantine directory instead of permanently deleting them. It also maintains JSON manifests to track original file locations and support file restoration.

## Features

- **Recursive File Scanning:** Scans files and subdirectories while collecting file names, absolute paths, and file sizes.
- **Duplicate Detection:** Uses SHA-256 fingerprints to identify files with identical contents, regardless of their filenames.
- **Large File Discovery:** Finds and sorts files exceeding a user-defined size threshold.
- **Cleanup Preview:** Generates a dry-run report showing duplicate groups, proposed files for quarantine, and potential storage recovery without modifying files.
- **Quarantine Management:** Moves selected duplicate files into a dedicated quarantine directory after explicit user confirmation.
- **File Restoration:** Restores quarantined files to their original locations using saved JSON manifests.
- **Conflict Handling:** Detects occupied restore destinations and reports conflicts rather than intentionally overwriting existing files.
- **Error Handling:** Handles common filesystem errors, inaccessible files, missing files, and invalid manifests.
- **Automated Testing:** Uses Python's built-in `unittest` framework to test duplicate detection, large-file discovery, quarantine, restoration, and conflict scenarios.

## Tech Stack

- **Python** — Core programming language
- **pathlib** — Filesystem paths and directory traversal
- **hashlib** — SHA-256 hashing for duplicate detection
- **argparse** — Command-line arguments and options
- **shutil** — File movement operations
- **json** — Quarantine manifests and restoration records
- **unittest** — Automated testing

No third-party Python packages are required.

## Project Structure

```text
safe-file-cleanup/
├── cleanup.py
├── test_cleanup.py
├── README.md
└── .cleanup_quarantine/
    └── session_001/
        ├── manifest.json
        └── files/
```

The quarantine directory and session files are created when duplicate files are moved.

## Getting Started

### Prerequisites

- Python 3.9 or later
- A terminal or command prompt
- Git (optional, for cloning the repository)

### Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/safe-file-cleanup.git
```

Navigate to the project directory:

```bash
cd safe-file-cleanup
```

Replace `YOUR_USERNAME` with your GitHub username.

## Usage

### 1. Scan a Directory

Scan a directory and its subdirectories to identify duplicate files and discover large files.

```bash
python cleanup.py "D:\Backup"
```

The program displays a scan summary, duplicate groups, a cleanup preview, and files exceeding the default size threshold of 100 MB.

The default mode does not intentionally move or delete files.

### 2. Find Large Files

Set a custom minimum file size in megabytes.

For example, find files larger than 500 MB:

```bash
python cleanup.py "D:\Backup" --min-size 500
```

Large files are displayed in descending order of size.

### 3. Preview and Quarantine Duplicates

Run the program with the quarantine option:

```bash
python cleanup.py "D:\Backup" --quarantine
```

The program displays the proposed duplicate files and requests explicit confirmation before moving them.

Type `QUARANTINE` to proceed. Any other response cancels the operation.

Duplicate detection keeps one copy from each detected group and proposes the remaining copies for quarantine.

### 4. Restore a Quarantine Session

Restore files from a previous quarantine session:

```bash
python cleanup.py restore session_001
```

Run the command from the directory containing `.cleanup_quarantine`, and replace `session_001` with the relevant session identifier.

The restoration process reads the session's JSON manifest and uses the recorded original paths to locate restoration destinations.

If a destination already exists, the program reports the conflict and leaves the quarantined file in place for manual resolution.

## Quarantine and Manifest

Each quarantine session contains a `manifest.json` file recording information about the files involved in the operation.

Example manifest entry:

```json
{
    "original_path": "D:\\Photos\\photo_copy.jpg",
    "quarantine_path": "D:\\Photos\\.cleanup_quarantine\\session_001\\files\\photo_copy.jpg",
    "size_bytes": 25165824,
    "sha256": "example-fingerprint",
    "status": "moved",
    "error": null
}
```

The fingerprint above is illustrative. The program records the actual SHA-256 hash.

The manifest helps track:

- Original file locations
- Quarantine file locations
- File sizes
- SHA-256 fingerprints
- Operation status
- Errors encountered during processing

This information supports restoration and helps identify files that need manual attention.

## Running Tests

The project uses Python's built-in `unittest` framework.

Run all tests from the project directory:

```bash
python -m unittest -v
```

The tests cover:

- Duplicate file detection
- Unique file handling
- Large-file discovery
- Quarantine and restoration
- Restore conflicts
- Invalid manifest handling

A successful test run confirms that the tested scenarios behave as expected. It does not guarantee protection against every possible filesystem failure.

## Safety Considerations

Safe File Cleanup is designed to make file cleanup more controlled and reviewable.

- The default scan mode is a dry run.
- Quarantining requires explicit confirmation.
- Files are moved to quarantine rather than permanently deleted.
- Restoration checks for existing destinations.
- JSON manifests record file locations and operation status.

Filesystem operations can still fail or be interrupted. Destination checks may also be affected by concurrent filesystem changes, and manifest updates may require manual recovery after an unexpected failure.

Always maintain backups of important data and test the tool with disposable files before using it on important directories.

## Limitations

- Duplicate detection compares file contents using SHA-256 hashes and requires reading files to calculate fingerprints.
- Large-file size refers to logical file size, not necessarily physical disk space occupied.
- The tool proposes duplicate copies based on the order in which files are discovered.
- Restore conflicts require manual resolution.
- A manifest is a recovery aid, not a guarantee that every interrupted operation can be recovered automatically.

## Future Improvements

- Add file-type and extension filters.
- Export scan reports to CSV or JSON.
- Add an interactive interface for reviewing cleanup proposals.
- Improve recovery for interrupted quarantine and restoration operations.
- Add more automated tests for filesystem errors and filename collisions.
- Add a dedicated command for listing available quarantine sessions.

## Purpose

This project was built to gain practical experience with Python file handling, hashing, dictionaries, command-line interfaces, JSON serialization, exception handling, filesystem operations, and automated testing.

The main goal is to make file cleanup more predictable by separating file analysis from cleanup actions and keeping a record of files moved into quarantine.
