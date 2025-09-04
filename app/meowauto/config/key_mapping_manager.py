import json
import os
from typing import Dict

DEFAULT_MAPPING: Dict[str, str] = {
    'L1': 'a', 'L2': 's', 'L3': 'd', 'L4': 'f', 'L5': 'g', 'L6': 'h', 'L7': 'j',
    'M1': 'q', 'M2': 'w', 'M3': 'e', 'M4': 'r', 'M5': 't', 'M6': 'y', 'M7': 'u',
    'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4', 'H5': '5', 'H6': '6', 'H7': '7'
}

class KeyMappingManager:
    """Manages persistent 21-key mapping (L/M/H x 1..7)."""
    def __init__(self, storage_path: str | None = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(base_dir, 'key_mapping.json')
        self.storage_path = storage_path or default_path
        self._mapping: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._mapping = {k: str(v) for k, v in data.items()}
                        return
        except Exception:
            pass
        self._mapping = DEFAULT_MAPPING.copy()

    def save(self) -> bool:
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._mapping, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def get_mapping(self) -> Dict[str, str]:
        # ensure all keys present
        m = DEFAULT_MAPPING.copy()
        m.update(self._mapping)
        return m

    def update_mapping(self, new_map: Dict[str, str]) -> None:
        filtered: Dict[str, str] = {}
        for region in ['L','M','H']:
            for d in ['1','2','3','4','5','6','7']:
                key = f"{region}{d}"
                if key in new_map and str(new_map[key]).strip():
                    filtered[key] = str(new_map[key]).strip()
        if filtered:
            self._mapping.update(filtered)

    def reset_default(self) -> None:
        self._mapping = DEFAULT_MAPPING.copy()
        self.save()
