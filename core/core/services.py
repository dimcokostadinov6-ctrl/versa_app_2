from dataclasses import dataclass
from typing import List, Tuple
from core.ports import IOCR, IRepository, Stroke

@dataclass
class SavePageService:
    repo: IRepository
    ocr: IOCR

    def save_drawn_page(self, image_path: str, ts_iso: str, clean_strokes: List[Stroke]) -> Tuple[int, int]:
        page_id = self.repo.add_page(image_path, ts_iso)
        entries = []
        try:
            entries = self.ocr.parse_strokes(clean_strokes) or []
        except Exception:
            entries = []
        for name, amount_st in entries:
            self.repo.add_entry(name=name, amount_st=amount_st, ts=ts_iso, page_id=page_id)
        return page_id, len(entries)
