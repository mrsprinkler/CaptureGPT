import sys
import ctypes
import json
import markdown

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QTextDocument,
)
from PySide6.QtWidgets import QApplication, QWidget

instructions = """
**`** — OCR-only screenshot
**Home** — Configuration mode
**Insert** — Show/hide overlay
**Escape** — Clear boxes and answer
**Delete** — Exit the program
**F9** — Change Reasoning Effort
**F10** — Screenshot + image to GPT
"""

starting_instructions = instructions + "\nOnce the application is ready, you may drag and resize this window."

# ================================================================
# Settings
# ================================================================

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"

SETTINGS_VERSION = 1


class Overlay(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        # ========================================================
        # OCR
        # ========================================================

        self.boxes = []

        # ========================================================
        # Answer
        # ========================================================

        self.answer_text = ""
        self.answer_visible = False
        self.answer_color = "white"

        # Default answer box geometry
        self.answer_x = 0
        self.answer_y = 0

        self.answer_width = 450
        self.answer_height = 250

        self.answer_padding = 15

        # ========================================================
        # SET button
        # ========================================================

        self.set_button_width = 100
        self.set_button_height = 45
        self.set_button_visible = False

        # ========================================================
        # Interaction
        # ========================================================

        self.click_through = False

        self.dragging_answer = False
        self.resizing_answer = False

        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.resize_start_x = 0
        self.resize_start_y = 0

        self.resize_start_width = 0
        self.resize_start_height = 0

        # ========================================================
        # Minimum answer box size
        # ========================================================

        self.min_answer_width = 250
        self.min_answer_height = 80

        # ========================================================
        # Maximum answer box size
        # ========================================================

        self.max_answer_width = 900
        self.max_answer_height = 700

        # ========================================================
        # Settings
        # ========================================================

        self.load_settings()

    # ============================================================
    # Settings
    # ============================================================

    def load_settings(self):
        """
        Load saved settings.

        If the file does not exist or contains invalid data,
        the default values from __init__ are used.
        """

        if not SETTINGS_FILE.exists():
            print("No settings.json found. Using defaults.")
            return

        try:
            with SETTINGS_FILE.open(
                "r",
                encoding="utf-8"
            ) as file:
                settings = json.load(file)

        except (OSError, json.JSONDecodeError) as error:
            print(
                f"Could not load settings.json: {error}"
            )
            print("Using default settings.")
            return

        # ========================================================
        # Check settings structure
        # ========================================================

        if not isinstance(settings, dict):
            print("Invalid settings.json structure.")
            print("Using default settings.")
            return

        version = settings.get(
            "version",
            1
        )

        if not isinstance(version, int):
            print("Invalid settings version.")
            print("Using default settings.")
            return

        # ========================================================
        # Future migrations can go here
        # ========================================================

        if version > SETTINGS_VERSION:
            print(
                "settings.json was created by a newer version "
                "of the application."
            )
            print("Using compatible default settings.")

            return

        # ========================================================
        # Answer box settings
        # ========================================================

        answer_settings = settings.get(
            "answer_box",
            {}
        )

        if not isinstance(answer_settings, dict):
            print("Invalid answer_box settings.")
            return

        self.answer_x = self.get_valid_number(
            answer_settings.get("x"),
            self.answer_x
        )

        self.answer_y = self.get_valid_number(
            answer_settings.get("y"),
            self.answer_y
        )

        self.answer_width = self.get_valid_number(
            answer_settings.get("width"),
            self.answer_width
        )

        self.answer_height = self.get_valid_number(
            answer_settings.get("height"),
            self.answer_height
        )

        # ========================================================
        # Make sure loaded dimensions are within limits
        # ========================================================

        self.answer_width = max(
            self.min_answer_width,
            min(
                self.answer_width,
                self.max_answer_width
            )
        )

        self.answer_height = max(
            self.min_answer_height,
            min(
                self.answer_height,
                self.max_answer_height
            )
        )

        print("Loaded settings.json")

    def get_valid_number(self, value, default):
        """
        Return a valid numeric setting or the supplied default.
        """

        if isinstance(value, bool):
            return default

        if isinstance(value, (int, float)):
            return value

        return default

    def save_settings(self):
        """
        Save only the settings owned by this class.
        Preserve every other setting already in settings.json.
        """

        settings = {}

        # Load the existing settings first
        if SETTINGS_FILE.exists():
            try:
                with SETTINGS_FILE.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)

                if isinstance(loaded, dict):
                    settings = loaded

            except (OSError, json.JSONDecodeError):
                pass

        # Update only our settings
        settings["version"] = SETTINGS_VERSION

        if not isinstance(settings.get("answer_box"), dict):
            settings["answer_box"] = {}

        settings["answer_box"].update({
            "x": self.answer_x,
            "y": self.answer_y,
            "width": self.answer_width,
            "height": self.answer_height,
        })

        try:
            with SETTINGS_FILE.open("w", encoding="utf-8") as file:
                json.dump(settings, file, indent=4)

            print("Saved settings.json")

        except OSError as error:
            print(f"Could not save settings.json: {error}")
        # ============================================================
        # OCR boxes
        # ============================================================

    def set_boxes(self, boxes):
        self.boxes = boxes
        self.update()

    # ============================================================
    # Answer text
    # ============================================================

    def set_answer(self, text=None, color="white"):
        if text is None or not text.strip():
            self.answer_text = ""
            self.answer_visible = False

        else:
            self.answer_text = text
            self.answer_color = color
            self.answer_visible = True

        self.update()
        QApplication.processEvents()

    # ============================================================
    # SET button visibility
    # ============================================================

    def show_set_button(self):
        self.set_button_visible = True
        self.update()

    def hide_set_button(self):
        self.set_button_visible = False
        self.update()

    # ============================================================
    # Markdown document
    # ============================================================

    def create_answer_document(self):
        print(self.answer_color)
        html = markdown.markdown(
            self.answer_text,
            extensions=[
                "fenced_code",
                "nl2br"
            ]
        )

        document = QTextDocument()

        document.setHtml(
            f"""
            <style>
                * {{
                    color: {self.answer_color};
                    font-family: Arial;
                    font-size: 16px;
                }}

                h1 {{
                    font-size: 24px;
                }}

                h2 {{
                    font-size: 20px;
                }}

                h3 {{
                    font-size: 18px;
                }}

                code {{
                    background-color: #333333;
                    padding: 2px;
                }}

                pre {{
                    background-color: #333333;
                    padding: 8px;
                }}

                li {{
                    margin-bottom: 4px;
                }}
            </style>

            {html}
            """
        )

        return document

    # ============================================================
    # Answer rectangle
    # ============================================================

    def get_answer_rect(self):
        return QRectF(
            self.answer_x,
            self.answer_y,
            self.answer_width,
            self.answer_height
        )

    # ============================================================
    # Resize handle rectangle
    # ============================================================

    def get_resize_handle_rect(self):
        handle_size = 18

        return QRectF(
            self.answer_x
            + self.answer_width
            - handle_size,

            self.answer_y
            + self.answer_height
            - handle_size,

            handle_size,
            handle_size
        )

    # ============================================================
    # SET button rectangle
    # ============================================================

    def get_set_button_rect(self):
        x = (
            self.width()
            - self.set_button_width
        ) // 2

        y = (
            self.height()
            - self.set_button_height
        ) // 2

        return QRectF(
            x,
            y,
            self.set_button_width,
            self.set_button_height
        )

    # ============================================================
    # Click-through
    # ============================================================

    def set_click_through(self, enabled):
        self.click_through = enabled

        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020

        user32 = ctypes.windll.user32

        hwnd = int(self.winId())

        style = user32.GetWindowLongW(
            hwnd,
            GWL_EXSTYLE
        )

        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT

        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style
        )

        self.update()

    # ============================================================
    # Mouse press
    # ============================================================

    def mousePressEvent(self, event):
        if self.click_through:
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position()

        # ========================================================
        # SET button
        # ========================================================

        if (
            self.set_button_visible
            and self.get_set_button_rect().contains(pos)
        ):
            print("SET clicked")

            self.answer_visible = False

            self.hide_set_button()
            self.set_click_through(True)

            return

        # ========================================================
        # Resize handle
        # ========================================================

        if (
            self.answer_visible
            and self.get_resize_handle_rect().contains(pos)
        ):
            print("Started resizing answer box")

            self.resizing_answer = True

            self.resize_start_x = pos.x()
            self.resize_start_y = pos.y()

            self.resize_start_width = self.answer_width
            self.resize_start_height = self.answer_height

            return

        # ========================================================
        # Answer box
        # ========================================================

        if (
            self.answer_visible
            and self.get_answer_rect().contains(pos)
        ):
            print("Started dragging answer box")

            self.dragging_answer = True

            self.drag_offset_x = (
                pos.x()
                - self.answer_x
            )

            self.drag_offset_y = (
                pos.y()
                - self.answer_y
            )

            return

    # ============================================================
    # Mouse move
    # ============================================================

    def mouseMoveEvent(self, event):
        if self.click_through:
            return

        pos = event.position()

        # ========================================================
        # Resize
        # ========================================================

        if self.resizing_answer:
            delta_x = (
                pos.x()
                - self.resize_start_x
            )

            delta_y = (
                pos.y()
                - self.resize_start_y
            )

            new_width = (
                self.resize_start_width
                + delta_x
            )

            new_height = (
                self.resize_start_height
                + delta_y
            )

            new_width = max(
                self.min_answer_width,
                min(
                    new_width,
                    self.max_answer_width
                )
            )

            new_height = max(
                self.min_answer_height,
                min(
                    new_height,
                    self.max_answer_height
                )
            )

            self.answer_width = new_width
            self.answer_height = new_height

            self.update()

            return

        # ========================================================
        # Drag
        # ========================================================

        if self.dragging_answer:
            self.answer_x = (
                pos.x()
                - self.drag_offset_x
            )

            self.answer_y = (
                pos.y()
                - self.drag_offset_y
            )

            # Keep the box on screen horizontally
            self.answer_x = max(
                0,
                min(
                    self.answer_x,
                    self.width()
                    - self.answer_width
                )
            )

            # Keep the box on screen vertically
            self.answer_y = max(
                0,
                min(
                    self.answer_y,
                    self.height()
                    - self.answer_height
                )
            )

            self.update()

    # ============================================================
    # Mouse release
    # ============================================================

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if (
            self.dragging_answer
            or self.resizing_answer
        ):
            self.save_settings()

        self.dragging_answer = False
        self.resizing_answer = False

    # ============================================================
    # Paint
    # ============================================================

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        # ========================================================
        # OCR boxes
        # ========================================================

        ocr_pen = QPen(
            QColor(255, 0, 0, 220)
        )

        ocr_pen.setWidth(2)

        painter.setPen(ocr_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for box in self.boxes:
            x1, y1, x2, y2 = box

            painter.drawRect(
                int(x1),
                int(y1),
                int(x2 - x1),
                int(y2 - y1)
            )

        # ========================================================
        # Answer box
        # ========================================================

        if self.answer_visible:
            self.draw_answer_box(painter)

        # ========================================================
        # SET button
        # ========================================================

        if self.set_button_visible:
            self.draw_set_button(painter)

        painter.end()

    # ============================================================
    # Draw answer box
    # ============================================================

    def draw_answer_box(self, painter):
        rect = self.get_answer_rect()

        # ========================================================
        # Background
        # ========================================================

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(
            QColor(20, 20, 20, 210)
        )

        painter.drawRoundedRect(
            rect,
            12,
            12
        )

        # ========================================================
        # Markdown
        # ========================================================

        document = self.create_answer_document()

        text_width = (
            self.answer_width
            - self.answer_padding * 2
        )

        document.setTextWidth(text_width)

        # ========================================================
        # Draw text
        # ========================================================

        painter.save()

        painter.translate(
            self.answer_x
            + self.answer_padding,

            self.answer_y
            + self.answer_padding
        )

        document.drawContents(
            painter,
            QRectF(
                0,
                0,
                text_width,
                self.answer_height
                - self.answer_padding * 2
            )
        )

        painter.restore()

        # ========================================================
        # Resize handle
        # ========================================================

        if not self.click_through:
            handle_size = 18

            handle_x = (
                self.answer_x
                + self.answer_width
                - handle_size
            )

            handle_y = (
                self.answer_y
                + self.answer_height
                - handle_size
            )

            painter.setPen(
                QPen(
                    QColor(255, 255, 255, 160),
                    2
                )
            )

            # Three diagonal resize lines
            painter.drawLine(
                int(handle_x + 6),
                int(handle_y + 14),
                int(handle_x + 14),
                int(handle_y + 6)
            )

            painter.drawLine(
                int(handle_x + 10),
                int(handle_y + 14),
                int(handle_x + 14),
                int(handle_y + 10)
            )

            painter.drawLine(
                int(handle_x + 14),
                int(handle_y + 14),
                int(handle_x + 14),
                int(handle_y + 14)
            )

    # ============================================================
    # Draw SET button
    # ============================================================

    def draw_set_button(self, painter):
        rect = self.get_set_button_rect()

        # ========================================================
        # Background
        # ========================================================

        painter.setPen(
            QPen(
                QColor(255, 255, 255, 220),
                2
            )
        )

        painter.setBrush(
            QColor(40, 40, 40, 230)
        )

        painter.drawRoundedRect(
            rect,
            8,
            8
        )

        # ========================================================
        # Text
        # ========================================================

        painter.setPen(
            QColor(255, 255, 255, 255)
        )

        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            "SET"
        )


def createWindow():
    app = QApplication(sys.argv)

    screen = app.primaryScreen()
    geometry = screen.geometry()

    print("Qt geometry:", geometry)
    print("Qt size:", screen.size())
    print("Qt DPR:", screen.devicePixelRatio())

    overlay = Overlay()

    overlay.setGeometry(geometry)

    print("Overlay geometry:", overlay.geometry())

    # ============================================================
    # Windows layered window
    # ============================================================

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000

    user32 = ctypes.windll.user32

    hwnd = int(overlay.winId())

    style = user32.GetWindowLongW(
        hwnd,
        GWL_EXSTYLE
    )

    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        style | WS_EX_LAYERED
    )

    # ============================================================
    # Exclude overlay from Windows screen capture
    # ============================================================

    WDA_EXCLUDEFROMCAPTURE = 0x00000011

    success = user32.SetWindowDisplayAffinity(
        hwnd,
        WDA_EXCLUDEFROMCAPTURE
    )

    if not success:
        print(
            "Warning: Could not exclude overlay from capture"
        )

    # ============================================================
    # Show
    # ============================================================

    overlay.show()

    overlay.set_answer(
        "# Starting...\n" + starting_instructions
    )
    QApplication.processEvents()
    return app, overlay, geometry, screen.devicePixelRatio()


if __name__ == "__main__":
    app, overlay, geometry, dpr = createWindow()
    try:
        sys.exit(app.exec())

    finally:
        overlay.save_settings()