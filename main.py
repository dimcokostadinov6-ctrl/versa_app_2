from infra.database_sqlite import SQLiteRepo
from core.services import SavePageService
from infra.mlkit_digital_ink import MLKitDigitalInkOCR

repo = SQLiteRepo()
ocr = MLKitDigitalInkOCR(lang_tag="bg")
service = SavePageService(repo=repo, ocr=ocr)

if __name__ == '__main__':
    from ui_kivy.app import VeresiyaApp
    VeresiyaApp(repo=repo, service=service).run()
