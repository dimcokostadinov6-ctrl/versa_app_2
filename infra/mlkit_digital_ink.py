# -*- coding: utf-8 -*-
from typing import List, Tuple
import re
from jnius import autoclass
from core.ports import IOCR, Stroke

# ML Kit classes
DigitalInkRecognition = autoclass('com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognition')
DigitalInkRecognizerOptions = autoclass('com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognizerOptions')
DigitalInkRecognitionModel = autoclass('com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognitionModel')
DigitalInkRecognitionModelIdentifier = autoclass('com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognitionModelIdentifier')
Ink = autoclass('com.google.mlkit.vision.digitalink.recognition.Ink')
InkPoint = autoclass('com.google.mlkit.vision.digitalink.recognition.Ink$Point')
InkStrokeBuilder = autoclass('com.google.mlkit.vision.digitalink.recognition.Ink$Stroke$Builder')
RemoteModelManager = autoclass('com.google.mlkit.common.model.RemoteModelManager')
DownloadConditions = autoclass('com.google.mlkit.common.model.DownloadConditions')
Tasks = autoclass('com.google.android.gms.tasks.Tasks')

def _await_task(task):
    return getattr(Tasks, "await")(task)
class MLKitDigitalInkOCR(IOCR):
    """
    Google ML Kit Digital Ink (on-device).
    Език: 'bg' (кирилица). Първо пускане сваля модела (интернет), после офлайн.
    """
    def __init__(self, lang_tag: str = "bg"):
        self.lang_tag = lang_tag
        self._recognizer = None

    def _ensure_model(self):
        if self._recognizer is not None:
            return
        ident = DigitalInkRecognitionModelIdentifier.fromLanguageTag(self.lang_tag)
        model = DigitalInkRecognitionModel.builder(ident).build()
        mgr = RemoteModelManager.getInstance()
        cond = DownloadConditions.Builder().build()
        _await_task(mgr.download(model, cond))
        opts = DigitalInkRecognizerOptions.builder(model).build()
        self._recognizer = DigitalInkRecognition.getClient(opts)

    def _ink_from_strokes(self, strokes: List[Stroke]):
        b = Ink.builder()
        for s in strokes:
            sb = InkStrokeBuilder()
            for (x, y) in s:
                sb.addPoint(InkPoint.create(float(x), float(y)))
            b.addStroke(sb.build())
        return b.build()

    def parse_strokes(self, strokes: List[Stroke]) -> List[Tuple[str, int]]:
        if not strokes:
            return []
        self._ensure_model()
        ink = self._ink_from_strokes(strokes)
        result = _await_task(self._recognizer.recognize(ink))
        cands = result.getCandidates()
        if cands is None or cands.isEmpty():
            return []
        text = cands.get(0).getText() or ""
        return self._parse_name_amount(text)

    def _parse_name_amount(self, text: str) -> List[Tuple[str, int]]:
        out: List[Tuple[str, int]] = []
        lines = [ln.strip() for ln in re.split(r'[\r\n]+', text) if ln.strip()]
        for ln in lines:
            m = re.search(r'([0-9]+(?:[\\.,][0-9]{1,2})?)\\s*$', ln.replace(' ', ''))
            if not m:
                continue
            raw = m.group(1).replace(',', '.')
            try:
                st = int(round(float(raw) * 100))
            except Exception:
                continue
            name = ln[:ln.rfind(m.group(1))].strip().rstrip('-:/.')
            if name:
                out.append((name, st))
        return out
