import os, time, threading
from datetime import datetime
from math import fabs
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, FadeTransition
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line, InstructionGroup, Fbo, ClearColor, ClearBuffers
from core.services import SavePageService

def is_strike(points, w, h):
    if len(points) < 12:
        return False
    xs = points[::2]; ys = points[1::2]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    bw, bh = maxx - minx, maxy - miny
    if bw < w * 0.45:  # дълга
        return False
    if bh > h * 0.08:  # почти хоризонтална
        return False
    pos = neg = 0; lastd = 0
    for i in range(2, len(xs)):
        dx = xs[i] - xs[i-1]
        if abs(dx) < 2:
            continue
        d = 1 if dx > 0 else -1
        if d != lastd and lastd != 0:
            if d > 0: pos += 1
            else: neg += 1
        lastd = d
    return (pos >= 1 and neg >= 1)

class DrawArea(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = 'vertical'
        self.padding = dp(8); self.spacing = dp(8)
        self.canvas_box = BoxLayout(size_hint=(1, 1)); self.add_widget(self.canvas_box)

        with self.canvas_box.canvas:
            Color(1,1,1,1); self.bg = Rectangle(size=self.canvas_box.size, pos=self.canvas_box.pos)
        self.grid_instr = InstructionGroup(); self.canvas_box.canvas.add(self.grid_instr)
        self._draw_grid()

        with self.canvas_box.canvas:
            Color(1, 0.6, 0, 0.7)
            self.guide = Rectangle(size=(dp(3), self.canvas_box.height), pos=(self.canvas_box.x, self.canvas_box.y))

        self.canvas_box.bind(size=self._update_all, pos=self._update_all)

        self.strokes = []
        self.pen_only = True

        self.canvas_box.bind(on_touch_down=self._on_touch_down, on_touch_move=self._on_touch_move)

    def _draw_grid(self):
        self.grid_instr.clear()
        with self.grid_instr:
            Color(0,0,0,0.06)
            y = self.canvas_box.y
            step = dp(24)
            while y < self.canvas_box.top:
                Line(points=[self.canvas_box.x, y, self.canvas_box.right, y], width=1)
                y += step

    def _update_all(self, *_):
        self.bg.size = self.canvas_box.size; self.bg.pos = self.canvas_box.pos
        self._draw_grid()
        ratio = 0.60 if self.canvas_box.height > self.canvas_box.width else 0.45
        x = self.canvas_box.x + self.canvas_box.width * ratio
        self.guide.size = (dp(3), self.canvas_box.height)
        self.guide.pos = (x, self.canvas_box.y)

    def set_pen_only(self, v: bool):
        self.pen_only = v

    def _is_stylus(self, touch) -> bool:
        dev = getattr(touch, 'device', '') or ''
        s = str(getattr(touch, 'profile', ''))
        name = str(touch)
        return any(k in str(dev).lower() for k in ('stylus','pen')) \
            or any(k in s.lower() for k in ('stylus','pen')) \
            or ('stylus' in name.lower()) or ('pen' in name.lower())

    def _on_touch_down(self, widget, touch):
        if not self.canvas_box.collide_point(*touch.pos):
            return False
        if self.pen_only and not self._is_stylus(touch):
            return False
        with self.canvas_box.canvas:
            Color(0,0,0,1)
            line = Line(points=[*touch.pos], width=2)
        stroke = {"points":[touch.x, touch.y], "width":2, "line": line, "is_strike": False}
        self.strokes.append(stroke)
        return True

    def _on_touch_move(self, widget, touch):
        if not self.canvas_box.collide_point(*touch.pos):
            return False
        if self.pen_only and not self._is_stylus(touch):
            return False
        if not self.strokes:
            return False
        s = self.strokes[-1]
        s["points"] += [touch.x, touch.y]
        s["line"].points = s["points"]
        s["is_strike"] = is_strike(s["points"], self.canvas_box.width, self.canvas_box.height)
        return True

    def clear(self):
        self.canvas_box.canvas.clear()
        with self.canvas_box.canvas:
            Color(1,1,1,1); self.bg = Rectangle(size=self.canvas_box.size, pos=self.canvas_box.pos)
        self.grid_instr = InstructionGroup(); self.canvas_box.canvas.add(self.grid_instr); self._draw_grid()
        with self.canvas_box.canvas:
            Color(1, 0.6, 0, 0.7)
            self.guide = Rectangle(size=(dp(3), self.canvas_box.height), pos=(self.canvas_box.x, self.canvas_box.y))
        self.strokes.clear()

    def export_masked_png(self, path: str):
        fbo = Fbo(size=self.canvas_box.size, with_stencilbuffer=True)
        with fbo:
            ClearColor(1,1,1,1); ClearBuffers()
            Color(0,0,0,1)
            for s in self.strokes:
                if s.get("is_strike"):
                    continue
                Line(points=s["points"], width=s["width"])
        fbo.draw()
        fbo.texture.save(path)

    def get_clean_strokes(self):
        clean = []
        for s in self.strokes:
            if s.get("is_strike"):
                continue
            pts = s["points"]
            clean.append([(pts[i], pts[i+1]) for i in range(0, len(pts), 2)])
        return clean

class SearchView(Screen):
    def __init__(self, repo, **kw):
        super().__init__(**kw); self.repo=repo
        root=BoxLayout(orientation='vertical')

        top=GridLayout(cols=3, size_hint=(1,None), height=dp(64), padding=[dp(12),0,dp(12),0], spacing=dp(8))
        with top.canvas.before: Color(0,0,0,1); self._r=Rectangle(size=top.size,pos=top.pos)
        top.bind(size=lambda *_: self._u(top), pos=lambda *_: self._u(top))
        back=Button(text='← Платно', size_hint=(None,1), width=dp(140)); back.bind(on_press=lambda *_: setattr(self.manager,'current','draw'))
        top.add_widget(back); top.add_widget(Label(text='Търсене', color=(1,1,1,1), font_size=dp(22))); top.add_widget(Label())
        root.add_widget(top)

        bar=BoxLayout(orientation='horizontal', size_hint=(1,None), height=dp(56), padding=[dp(12),dp(8)], spacing=dp(8))
        self.search=TextInput(hint_text='🔍 Въведи точно име…', multiline=False, font_size=dp(18))
        btn=Button(text='Търси'); btn.bind(on_press=self.on_search)
        bar.add_widget(self.search); bar.add_widget(btn); root.add_widget(bar)

        self.results=Label(text='', halign='left', valign='top', markup=True)
        self.results.bind(size=lambda *_: setattr(self.results, 'text_size', self.results.size))
        sv=ScrollView(); sv.add_widget(self.results); root.add_widget(sv)

        self.add_widget(root)

    def _u(self,w): self._r.size=w.size; self._r.pos=w.pos

    def on_search(self,*_):
        name = (self.search.text or '').strip()
        if not name:
            self.results.text = 'Въведи точно име.'
            return
        rows = self.repo.list_entries(name)
        total = self.repo.sum_for_name(name)
        if not rows:
            self.results.text = f'Няма записи за [b]{name}[/b].'
            return
        lines = [f'[b]{name}[/b] — {len(rows)} запис(а):']
        for (ts, st, page_id) in rows:
            lv = f'{st/100:.2f} лв'
            pid = f' (стр. #{page_id})' if page_id is not None else ''
            lines.append(f'• {ts} — {lv}{pid}')
        lines.append(f'\n[b]Общо: {total/100:.2f} лв[/b]')
        self.results.text = '\n'.join(lines)

class DrawView(Screen):
    def __init__(self, service: SavePageService, repo, **kw):
        super().__init__(**kw); self.service=service; self.repo=repo
        root=BoxLayout(orientation='vertical')

        top=GridLayout(cols=4, size_hint=(1,None), height=dp(64), padding=[dp(12),0,dp(12),0], spacing=dp(8))
        with top.canvas.before: Color(0,0.4,1,1); self._r=Rectangle(size=top.size,pos=top.pos)
        top.bind(size=lambda *_:self._u(top), pos=lambda *_:self._u(top))

        self.pen_btn = Button(text='Само писалка: Вкл')
        self.pen_btn.bind(on_press=self.toggle_pen)
        btn_clear=Button(text='Изчисти'); btn_clear.bind(on_press=lambda *_: self.draw.clear())
        btn_save=Button(text='Запази'); btn_save.bind(on_press=self.on_save)
        btn_search=Button(text='Търсене'); btn_search.bind(on_press=lambda *_: setattr(self.manager,'current','search'))

        top.add_widget(self.pen_btn); top.add_widget(btn_clear); top.add_widget(btn_save); top.add_widget(btn_search)
        root.add_widget(top)

        self.draw=DrawArea()
        root.add_widget(self.draw)

        self.status=Label(text='Готово', size_hint=(1,None), height=dp(28))
        root.add_widget(self.status)

        self.add_widget(root)

    def _u(self,w): self._r.size=w.size; self._r.pos=w.pos

    def toggle_pen(self, *_):
        self.draw.set_pen_only(!self.draw.pen_only)  # flip
        self.pen_btn.text = f"Само писалка: {'Вкл' if self.draw.pen_only else 'Изкл'}"

    def on_save(self,*_):
        os.makedirs('pages', exist_ok=True)
        ts=time.strftime('%Y%m%d_%H%M%S'); path=f'pages/page_{ts}.png'
        try:
            self.draw.export_masked_png(path)
        except Exception as e:
            self.status.text=f'Грешка: {e}'; return

        clean_strokes = self.draw.get_clean_strokes()
        self.status.text='Разчитане и запис...'

        def worker():
            pid, n = self.service.save_drawn_page(path, datetime.now().isoformat(timespec='seconds'), clean_strokes)
            def ui_update(dt):
                self.status.text=f'Запазено (страница #{pid}). Редове: {n}. PNG: {path}'
                self.draw.clear()
            Clock.schedule_once(ui_update, 0)

        threading.Thread(target=worker, daemon=True).start()

class VeresiyaApp(App):
    def __init__(self, repo, service, **kw):
        super().__init__(**kw); self.repo=repo; self.service=service
    def build(self):
        sm=ScreenManager(transition=FadeTransition()); self.repo.init()
        sm.add_widget(DrawView(self.service, self.repo, name='draw'))
        sm.add_widget(SearchView(self.repo, name='search'))
        sm.current='draw'
        return sm
