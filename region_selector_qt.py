from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor

class QtRegionSelector(QWidget):
    """
    Overlay transparan full screen untuk memilih kotak area layar (ROI)
    secara interaktif dengan klik & drag mouse pada resolusi penuh virtual screen.
    Murni PySide6, DPI-aware, tanpa dependensi Tkinter.
    """
    def __init__(self, on_selected_callback, title=None, parent=None):
        super().__init__(parent)
        self.on_selected_callback = on_selected_callback
        self.title = title or "KLIK & DRAG MOUSE UNTUK MEMILIH AREA SCANNER (ROI)"
        self.start_pos = None
        self.current_pos = None
        self.is_dragging = False

        # Konfigurasi Window Overlay
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setCursor(Qt.CrossCursor)

        # Meliputi seluruh virtual screen (multi-monitor)
        virtual_geom = QRect()
        for screen in QApplication.screens():
            virtual_geom = virtual_geom.united(screen.geometry())
        self.setGeometry(virtual_geom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Latar belakang gelap semi-transparan
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # Petunjuk Header di Layar Atas
        painter.setPen(QColor("#00ffcc"))
        font = QFont("Segoe UI", 14, QFont.Bold)
        painter.setFont(font)
        hint_text = f"{self.title}\n(Tekan ESC atau Klik Kanan untuk Batal)"
        painter.drawText(QRect(0, 50, self.width(), 70), Qt.AlignHCenter | Qt.AlignTop, hint_text)

        # Kotak Seleksi saat Drag
        if self.start_pos and self.current_pos:
            rect = QRect(self.start_pos, self.current_pos).normalized()

            # Highlight fill putih lembut
            painter.fillRect(rect, QColor(255, 255, 255, 35))

            # Border neon hijau tajam
            pen = QPen(QColor("#a2c73e"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Label Ukuran Dimensi (W x H px)
            dim_text = f"{rect.width()} x {rect.height()} px"
            painter.setPen(QColor("#ffff00"))
            dim_font = QFont("Segoe UI", 11, QFont.Bold)
            painter.setFont(dim_font)
            text_y = rect.top() - 8 if rect.top() >= 30 else rect.bottom() + 18
            painter.drawText(rect.left() + 4, text_y, dim_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.position().toPoint()
            self.current_pos = self.start_pos
            self.is_dragging = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.current_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            if self.start_pos and self.current_pos:
                rect = QRect(self.start_pos, self.current_pos).normalized()
                self.close()
                if rect.width() > 15 and rect.height() > 15:
                    screen_pos = self.mapToGlobal(rect.topLeft())
                    selected_area = {
                        "left": int(screen_pos.x()),
                        "top": int(screen_pos.y()),
                        "width": int(rect.width()),
                        "height": int(rect.height())
                    }
                    if self.on_selected_callback:
                        self.on_selected_callback(selected_area)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
