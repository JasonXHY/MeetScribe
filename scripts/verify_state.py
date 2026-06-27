import sys, os, time
sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
app = QApplication(sys.argv)
from gui.app import MeetScribeApp
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

test_app = MeetScribeApp()
test_audio = r'C:\侧耳倾听\tests\fixtures\test_meeting_16min.wav'
test_app.file_manager.add_file(test_audio)
time.sleep(1)

handler = test_app._transcription_handler
fmt = test_app._home_page.get_selected_format()
handler.start([test_audio], fmt, {}, '')
start = time.time()
while handler.is_transcribing and (time.time() - start) < 300:
    app.processEvents()
    time.sleep(1)

item = test_app.file_manager.get_file(test_audio)
print("=== Backend ===")
print("  status:", item.status.value)
print("  topic:", repr(getattr(item, 'topic', '')))
print("  result_path:", item.result_path)

table = test_app._home_page._file_list_view._table
for row in range(table.rowCount()):
    name_item = table.item(row, 1)
    if name_item and "16min" in name_item.text():
        status_item = table.item(row, 5)
        icon = status_item.icon() if status_item else None
        has_icon = bool(icon and not icon.isNull()) if icon else False
        tooltip = status_item.toolTip() if status_item else ""
        topic_item = table.item(row, 2)
        topic_text = topic_item.text() if topic_item else ""
        print("=== Table ===")
        print("  status icon present:", has_icon)
        print("  status tooltip:", tooltip)
        print("  topic:", repr(topic_text))
        btn_cell = table.cellWidget(row, 6)
        if btn_cell:
            btns = btn_cell.findChildren(QPushButton)
            tips = [b.toolTip() for b in btns]
            print("  buttons:", len(btns), "tooltips:", tips)
        break

test_app.close()
