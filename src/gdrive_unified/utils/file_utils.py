"""File utility functions."""
# MATURE CODE. DO NOT TOUCH THIS FILE WITHOUT SPECIFIC INSTRUCTIONS


import hashlib
import re
from pathlib import Path
from typing import Optional


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_filename(filename: str, max_length: int = 200) -> str:
    """Clean a filename to be filesystem-safe."""
    # Remove or replace problematic characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove multiple consecutive underscores
    cleaned = re.sub(r'_{2,}', '_', cleaned)
    
    # Trim whitespace and remove leading/trailing underscores
    cleaned = cleaned.strip().strip('_')
    
    # Truncate if too long
    if len(cleaned) > max_length:
        name, ext = Path(cleaned).stem, Path(cleaned).suffix
        max_name_length = max_length - len(ext)
        cleaned = name[:max_name_length] + ext
    
    return cleaned


def get_file_hash(file_path: Path, algorithm: str = "md5") -> str:
    """Calculate hash of a file."""
    hash_func = getattr(hashlib, algorithm)()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def find_similar_files(target_name: str, candidates: list, threshold: float = 0.7) -> Optional[Path]:
    """Find the most similar file from a list of candidates."""
    from difflib import SequenceMatcher
    
    best_match = None
    best_score = 0
    
    target_stem = Path(target_name).stem.lower()
    
    for candidate in candidates:
        candidate_stem = Path(candidate).stem.lower()
        score = SequenceMatcher(None, target_stem, candidate_stem).ratio()
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    return best_match
