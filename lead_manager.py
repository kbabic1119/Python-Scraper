"""
Lead Manager — Individual Lead Control
Handles delete, archive, restore operations on lead CSV files.
"""

import pandas as pd
import os


ARCHIVE_FILE = "archived_leads.csv"


def get_active_csv():
    """Get the most advanced CSV file currently available."""
    for fname in ["deep_extracted_leads.csv", "enriched_leads.csv", "pain_scored_leads.csv", "leads.csv"]:
        if os.path.exists(fname) and os.path.getsize(fname) > 0:
            return fname
    return None


def delete_leads(csv_file, indices):
    """Delete leads at specified indices from the CSV file."""
    if not os.path.exists(csv_file):
        return 0
    df = pd.read_csv(csv_file)
    before = len(df)
    df = df.drop(index=[i for i in indices if i in df.index]).reset_index(drop=True)
    df.to_csv(csv_file, index=False)
    return before - len(df)


def archive_leads(csv_file, indices):
    """Move leads at specified indices to archive file."""
    if not os.path.exists(csv_file):
        return 0
    df = pd.read_csv(csv_file)
    to_archive = df.loc[[i for i in indices if i in df.index]]

    if len(to_archive) == 0:
        return 0

    # Append to archive
    if os.path.exists(ARCHIVE_FILE):
        existing = pd.read_csv(ARCHIVE_FILE)
        combined = pd.concat([existing, to_archive], ignore_index=True)
        combined.to_csv(ARCHIVE_FILE, index=False)
    else:
        to_archive.to_csv(ARCHIVE_FILE, index=False)

    # Remove from active file
    df = df.drop(index=[i for i in indices if i in df.index]).reset_index(drop=True)
    df.to_csv(csv_file, index=False)
    return len(to_archive)


def restore_all_archived():
    """Restore all archived leads back to leads.csv."""
    if not os.path.exists(ARCHIVE_FILE):
        return 0
    archived = pd.read_csv(ARCHIVE_FILE)
    if len(archived) == 0:
        return 0

    target = "leads.csv"
    if os.path.exists(target):
        existing = pd.read_csv(target)
        combined = pd.concat([existing, archived], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Website URL"], keep="first")
        combined.to_csv(target, index=False)
    else:
        archived.to_csv(target, index=False)

    count = len(archived)
    os.remove(ARCHIVE_FILE)
    return count


def get_archived_count():
    """Get number of archived leads."""
    if not os.path.exists(ARCHIVE_FILE):
        return 0
    try:
        return len(pd.read_csv(ARCHIVE_FILE))
    except Exception:
        return 0
