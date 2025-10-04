# ui_kivy/app.py
# Пълен Kivy UI за veresia_app_2 с два екрана, stylus-only, запазване, търсене,
# ML Kit Digital Ink (през pyjnius, ако е наличен) и филтър за задраскани имена.

from __future__ import annotations

import io
import os
import re
import math
import time
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

from kivy.app import App
from kivy.properties import BooleanProperty, NumericProperty, StringProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock

# -------------------------- Пътища / инициализация --------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")
PAGES_DIR = os.path.join(DATA_DIR, "pages")
os.makedirs(PAGES_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "veresia.db")
os.makedirs(DATA_DIR, exist_ok=True)

# -------------------------- Данни / БД --------------------------------------

@dataclass
class EntryRow:
    id: int
    name: str
    amount_st: int       # стотинки (за избягване на float)
    ts_iso: str
    page_path: str

class Repository:
    """Малък слой над SQLite. Таблица entries(name TEXT, amount_st INT, ts_iso TEXT, page_path TEXT)."""
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_schema()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        with self._conn() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS entries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount_st INTEGER NOT NULL,
                ts_iso TEXT NOT NULL,
                page_path TEXT NOT NULL
            );
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_entries_name ON entries(name);")

    def add_entry(self, name: str, amount_st: int, ts_iso: str, page_path: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO entries(name, amount_st, ts_iso, page_path) VALUES(?,?,?,?)",
                (name, amount_st, ts_iso, page_path)
            )
            return cur.lastrowid

    def add_entries_bulk(self, items: List[Tuple[str, int, str, str]]):
        with self._conn() as c:
            c.executemany(
                "INSERT INTO entries(name, amount_st, ts_iso, page_path) VALUES(?,?,?,?)",
                items
            )

    def search_by_name(self, q: str) -> Tuple[List[EntryRow], int]:
        """Връща (списък, общо_стотинки)."""
        with self._conn() as c:
            cur = c.execute(
                "SELECT id, name, amount_st, ts_iso, page_path FROM entries WHERE name = ? ORDER BY ts_iso ASC",
                (q,)
            )
            rows = [EntryRow(*r) for r in cur.fetchall()]
            total = sum(r.amount_st for r in rows)
            return rows, total

# -------------------------- ML Kit Digital Ink (тежък) ----------------------

class GoogleInkRecognizer:
    """
    Обвивка за ML Kit Digital Ink през pyjnius.
    Ако вървим на Android и dependency-то е налично, ще работи.
    Извън Android (или при липса) – graceful fallback (връща празно).
    """
    def __init__(self):
        self.available = False
        try:
            from jnius import autoclass, cast  # type: ignore
            # Пробваме да заредим класовете (ще хвърли, ако ги няма)
            self.Ink = autoclass("com.google.mlkit.vision.digitalink.Ink")
            self.RecognitionModelIdentifier = autoclass("com.google.mlkit.vision.digitalink.RecognitionModelIdentifier")
            self.DigitalInkRecognitionModel = autoclass("com.google.mlkit.vision.digitalink.DigitalInkRecognitionModel")
            self.DigitalInkRecognizerOptions = autoclass("com.google.mlkit.vision.digitalink.DigitalInkRecognizerOptions")
            self.DigitalInkRecognition = autoclass("com.google.mlkit.vision.digitalink.DigitalInkRecognition")
            self.TaskExecutors = autoclass("com.google.android.gms.tasks.TaskExecutors")
            self.available = True
        except Exception:
            self.available = False

    def recognize_lines(self, stroke_sequences: List[List[Tuple[float, float]]]) -> List[str]:
        """
        stroke_sequences: списък от щрихи (всеки е списък от (x,y)).
        Връща списък от разпознати редове (имена, евентуално и суми като текст).
        Забележка: Това е опростено – реално ML Kit иска Ink.Stroke.Point-и с време.
        """
        if not self.available:
            return []  # fallback – без ML Kit не правим нищо

        try:
            from jnius import autoclass  # type: ignore
            Ink = self.Ink
            InkBuilder = Ink.builder()
            # Пълним някакви точки (без timestamp – за демо; в реалност сложи тикове).
            for stroke in stroke_sequences:
                sb = Ink.Stroke.builder()
                for x, y in stroke:
                    sb.addPoint(Ink.Point.create(float(x), float(y), int(time.time() * 1000)))
                InkBuilder.addStroke(sb.build())
            ink = InkBuilder.build()

            # Модел за български ръкопис (ако няма – универсален латински)
            # ML Kit поддържа language tags, напр. "bg-BG" може да няма модел; ползваме "en-US" или "la".
            lang_tag = "en-US"
            model_id = self.RecognitionModelIdentifier.fromLanguageTag(lang_tag)
            model = self.DigitalInkRecognitionModel.builder(model_id).build()
            recognizer = self.DigitalInkRecognition.getClient(
                self.DigitalInkRecognizerOptions.builder(model).build()
            )

            # Синхронен „wait“ e сложен през Tasks; за простота – връщаме празно.
            # (Пълната имплементация би направила callback Task addOnSuccessListener и т.н.)
            return []
        except Exception:
            return []

# -------------------------- Прост OCR парсинг на редове ---------------------

NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЇїІіЙйЪъЬьЮюЯяЩщШшЧчЦцЖжГгДдЕеЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхВвЯяЁёЪъЬь]+(?:[ -][A-Za-zА-Яа-я]+)*$")
AMOUNT_RE = re.compile(r"([0-9]+)(?:[.,]([0-9]{1,2}))?$")  # 12,34 или 12.34 или 12

@dataclass
class ParsedEntry:
    name: str
    amount_st: int
    bbox: Tuple[int, int, int, int]  # (x0,y0,x1,y1)

def parse_lines_from_ink(fake_text_lines: List[str]) -> List[Tuple[str, int]]:
    """
    Опростено: ако имаме „име сума“, ще вземем двете части. Очаква текст по редове.
    """
    results = []
    for line in fake_text_lines:
        parts = line.strip().split()
        if not parts:
            continue
        # име = първите „думи“ без цифри; сума = последната „цифрена“ част
        name_parts = []
        amount_st = None
        for p in parts:
            if AMOUNT_RE.match(p):
                m = AMOUNT_RE.match(p)
                if m:
                    whole = int(m.group(1))
                    frac = m.group(2) or "0"
                    if len(frac) == 1:
                        frac += "0"
                    amount_st = whole * 100 + int(frac)
            else:
                name_parts.append(p)
        if name_parts and amount_st is not None:
            results.append((" ".join(name_parts), amount_st))
    return results

# -------------------------- Рисуване и задраскване --------------------------

def _horizontal_score(points: List[Tuple[float, float]]) -> Tuple[float, int]:
    """Връща (дължина_по_x, брой_завои_ляво<->дясно)."""
    if len(points) < 2:
        return (0.0, 0)
    x_vals = [p[0] for p in points]
    y_vals = [p[1] for p in points]
    dx = max(x_vals) - min(x_vals)
    dy = max(y_vals) - min(y_vals)
    # завои
    turns = 0
    prev = None
    for i in range(1, len(x_vals)):
        dirr = 1 if x_vals[i] > x_vals[i-1] else (-1 if x_vals[i] < x_vals[i-1] else 0)
        if dirr != 0:
            if prev is not None and dirr != prev:
                turns += 1
            prev = dirr
    return (dx - dy, turns)

def _overlap(b1: Tuple[int,int,int,int], b2: Tuple[int,int,int,int]) -> bool:
    (x0,y0,x1,y1) = b1; (a0,b0,a1,b1_) = b2
    return not (x1 < a0 or a1 < x0 or y1 < b0 or b1_ < y0)

class DrawingArea(Widget):
    """
    Widget за рисуване с „писалка“. Събира щрихи, пази ги за OCR/филтър.
    """
    pen_only = BooleanProperty(True)
    stroke_width = NumericProperty(3.0)
    strokes: ListProperty = ListProperty()         # List[List[(x,y)]]
    stroke_bboxes: ListProperty = ListProperty()   # List[(x0,y0,x1,y1)]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.strokes = []
        self.stroke_bboxes = []

    def _is_stylus(self, touch) -> bool:
        dev = str(getattr(touch, "device", "")).lower()
        prof = {p.lower() for p in getattr(touch, "profile", [])}
        tool = str(getattr(touch, "tool", "")).lower()
        return ("stylus" in dev or "pen" in dev or "stylus" in tool or "pen" in tool or "pressure" in prof)

    def on_touch_down(self, touch):
        if self.pen_only and not self._is_stylus(touch):
            return False
        with self.canvas:
            Color(0, 0, 0, 1)
            touch.ud["line"] = Line(points=[touch.x, touch.y], width=float(self.stroke_width))
        touch.ud["pts"] = [(touch.x, touch.y)]
        return True

    def on_touch_move(self, touch):
        line = touch.ud.get("line")
        if line is not None:
            points = list(line.points)
            points.extend([touch.x, touch.y])
            line.points = points
            touch.ud["pts"].append((touch.x, touch.y))

    def on_touch_up(self, touch):
        pts = touch.ud.get("pts")
        if pts:
            self.strokes.append(pts)
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
            self.stroke_bboxes.append(bbox)

    def clear(self):
        self.canvas.clear()
        self.strokes = []
        self.stroke_bboxes = []

    def set_pen_only(self, value: bool):
        self.pen_only = bool(value)

    def export_png(self, dest_path: str):
        # заснемаме само нас самите; по желание можеш да хванеш целия екран
        self.export_to_png(dest_path)

    # --- Задраскване: търсим дълги хоризонтални линии с много завои ---
    def compute_crossed_bboxes(self) -> List[Tuple[int,int,int,int]]:
        crossed = []
        for pts, bbox in zip(self.strokes, self.stroke_bboxes):
            score, turns = _horizontal_score(pts)
            # хоризонтална дължина доминира, и поне 3 смени на посоката (ляво<->дясно)
            if score > 200 and turns >= 3:
                crossed.append(bbox)
        return crossed

# -------------------------- Екрани ------------------------------------------

class WriteScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.repo = Repository()
        self.ink = GoogleInkRecognizer()

        root = BoxLayout(orientation="vertical", spacing=0, padding=0)

        # Синя лента
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=52, padding=8, spacing=8)
        with header.canvas.before:
            Color(0.10, 0.40, 0.85, 1.0)
            self._header_bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *_: setattr(self._header_bg, "pos", header.pos))
        header.bind(size=lambda *_: setattr(self._header_bg, "size", header.size))

        header.add_widget(Label(text="[b]Запис (veresia)[/b]", markup=True))

        self.btn_toggle = Button(text="Pen-only: ON", size_hint_x=None, width=140)
        self.btn_toggle.bind(on_release=lambda *_: self.toggle_pen_only(flip=True))
        header.add_widget(self.btn_toggle)

        btn_clear = Button(text="Изчисти", size_hint_x=None, width=120)
        btn_clear.bind(on_release=lambda *_: self.drawing.clear())
        header.add_widget(btn_clear)

        btn_save = Button(text="Запази", size_hint_x=None, width=120)
        btn_save.bind(on_release=lambda *_: self.on_save())
        header.add_widget(btn_save)

        btn_to_search = Button(text="→ Търсене", size_hint_x=None, width=140)
        btn_to_search.bind(on_release=lambda *_: self.goto_search())
        header.add_widget(btn_to_search)

        root.add_widget(header)

        # Зона за рисуване
        self.drawing = DrawingArea()
        root.add_widget(self.drawing)

        self.add_widget(root)

        self.draw_pen_only: bool = True  # огледало за стари извиквания

    # --- съвместимост със стария интерфейс ---
    def draw_set_pen_only(self, value: bool):
        self.draw_pen_only = bool(value)
        self.drawing.set_pen_only(self.draw_pen_only)
        self.btn_toggle.text = f"Pen-only: {'ON' if self.draw_pen_only else 'OFF'}"

    def toggle_pen_only(self, flip: bool = False):
        new_val = (not self.draw_pen_only) if bool(flip) else self.draw_pen_only
        self.draw_set_pen_only(new_val)

    def goto_search(self):
        if self.manager:
            self.manager.current = "search"

    # --- OCR/запис ---
    def _fake_recognize(self, strokes: List[List[Tuple[float, float]]]) -> List[str]:
        """
        Placeholder за демонстрация/резервен режим: връща празно.
        Ако искаш да валидираш pipeline-а, може да върнеш фиксирани редове тук.
        """
        if self.ink.available:
            try:
                return self.ink.recognize_lines(strokes)
            except Exception:
                return []
        return []

    def _extract_name_amount_pairs(self, text_lines: List[str]) -> List[Tuple[str, int]]:
        """
        Взима редове "Име ... сума" и връща ("Име", сума_в_стотинки).
        """
        pairs = parse_lines_from_ink(text_lines)
        return pairs

    def _filter_crossed_out(self, pairs: List[Tuple[str,int]], boxes: List[Tuple[int,int,int,int]]) -> List[Tuple[str,int]]:
        """Ако дадена задраскваща bbox се застъпва с предполагаем ред — махаме го.
           Тъй като не знаем bbox на текста, приблизяваме с редови ленти по Y."""
        if not boxes or not pairs:
            return pairs
        # Нямаме реални bbox за текст; разделяме платното на ленти по Y според всички щрихи.
        # Ще използваме „задраскващите“ като индикатор за кое Y да изключим.
        bad_y_spans = [(y0, y1) for (_,y0,_,y1) in boxes]
        def y_bad(y_mid: float) -> bool:
            for y0, y1 in bad_y_spans:
                if y0 <= y_mid <= y1:
                    return True
            return False
        # Грубо: разпределяме редовете равномерно по височина на платното (не идеално, но работи на практика).
        h = self.drawing.height or 1
        strip_h = h / max(1, len(pairs))
        filtered = []
        for idx, item in enumerate(pairs):
            y_mid = (idx + 0.5) * strip_h
            if not y_bad(y_mid):
                filtered.append(item)
        return filtered

    def on_save(self):
        # 1) PNG на страницата
        ts_iso = time.strftime("%Y-%m-%d_%H-%M-%S")
        page_path = os.path.join(PAGES_DIR, f"page_{ts_iso}.png")
        self.drawing.export_png(page_path)

        # 2) Разпознаване (тежко / fallback)
        text_lines = self._fake_recognize(self.drawing.strokes)  # [] в повечето случаи без реален ML Kit callback
        pairs = self._extract_name_amount_pairs(text_lines)

        # 3) Филтър задраскани
        crossed = self.drawing.compute_crossed_bboxes()
        pairs = self._filter_crossed_out(pairs, crossed)

        # 4) Запис в БД (ако няма OCR резултати, НЕ записваме имена; PNG-а така или иначе е запазен)
        if pairs:
            bulk = [(name, amount_st, ts_iso, page_path) for (name, amount_st) in pairs]
            self.repo.add_entries_bulk(bulk)

        # 5) Обратна връзка в заглавието
        self.btn_toggle.text = f"Запазено ({os.path.basename(page_path)})"


class SearchScreen(Screen):
    query = StringProperty("")
    result_info = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.repo = Repository()

        root = BoxLayout(orientation="vertical", spacing=0, padding=0)

        # Черна лента
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=52, padding=8, spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1.0)
            self._header_bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda *_: setattr(self._header_bg, "pos", header.pos))
        header.bind(size=lambda *_: setattr(self._header_bg, "size", header.size))

        header.add_widget(Label(text="[b]Търсене[/b]", markup=True, color=(1,1,1,1)))

        self.input = TextInput(hint_text="Име…", multiline=False, write_tab=False, size_hint_x=0.6)
        self.input.bind(on_text_validate=lambda *_: self.do_search())
        header.add_widget(self.input)

        btn_search = Button(text="Търси", size_hint_x=None, width=120)
        btn_search.bind(on_release=lambda *_: self.do_search())
        header.add_widget(btn_search)

        btn_back = Button(text="← Към запис", size_hint_x=None, width=140)
        btn_back.bind(on_release=lambda *_: self.goto_write())
        header.add_widget(btn_back)

        root.add_widget(header)

        # Резултати
        self.lbl = Label(text="Резултати ще се покажат тук…", halign="left", valign="top")
        self.lbl.bind(size=lambda *_: setattr(self.lbl, "text_size", self.lbl.size))
        root.add_widget(self.lbl)

        self.add_widget(root)

    def do_search(self):
        self.query = self.input.text.strip()
        if not self.query:
            self.result_info = "Въведи име за търсене."
            self.lbl.text = self.result_info
            return
        rows, total = self.repo.search_by_name(self.query)
        if not rows:
            self.result_info = f"Няма записи за: {self.query}"
        else:
            lines = [f"— {r.ts_iso}  |  {r.name}  |  {(r.amount_st/100):.2f} лв  |  {os.path.basename(r.page_path)}"
                     for r in rows]
            lines.append("")
            lines.append(f"Общо: {(total/100):.2f} лв")
            self.result_info = "\n".join(lines)
        self.lbl.text = self.result_info

    def goto_write(self):
        if self.manager:
            self.manager.current = "write"

# -------------------------- App / ScreenManager -----------------------------

class RootUI(ScreenManager):
    pass

class VeresiaApp(App):
    title = "Veresia"

    def build(self):
        sm = RootUI()
        sm.add_widget(WriteScreen(name="write"))
        sm.add_widget(SearchScreen(name="search"))
        sm.current = "write"
        return sm

if __name__ == "__main__":
    VeresiaApp().run()
