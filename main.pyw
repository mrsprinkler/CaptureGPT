"""
"courses": [
    "AP Computer Science",
    "AP Environmental Science",
    "AP Precalculus",
    "AP Statistics",
    "Economics",
    "English 4"
  ]"""
print("Starting...")

import window

app, overlay, geometry, dpr = window.createWindow()


def printStatus(status):
    overlay.set_answer("# " + status + "\n" + window.starting_instructions)


import os
import sys
import threading
import queue
from pathlib import Path
from datetime import datetime
import json
import win32gui
import re
from PIL import Image
from pypdf import PdfReader, PdfWriter
import io
import img2pdf
from app_config import APP_DIR, load_settings, update_settings

def get_window_title():
    excluded = {
        "python",
        "System tray overflow window.",
        "Program Manager",
        "pythonw"
    }

    result = None

    def callback(hwnd, _):
        nonlocal result

        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()

        if title and title not in excluded:
            result = title
            return False

    win32gui.EnumWindows(callback, None)

    return result


# ============================================================
# Screenshot saving
# ============================================================

SETTINGS = load_settings()

OUTPUT_SETTINGS = SETTINGS["output"]
SAVE_MARKDOWN = OUTPUT_SETTINGS["save_markdown"]
SAVE_PDF = OUTPUT_SETTINGS["save_pdf"]

output_directory_value = OUTPUT_SETTINGS["directory"]
output_directory = Path(output_directory_value)
if not output_directory.is_absolute():
    output_directory = APP_DIR / output_directory

screenshot_folder = output_directory
screenshot_folder.mkdir(parents=True, exist_ok=True)


def get_answers_folder():
    folder = screenshot_folder

    settings = load_settings()

    answers_settings = settings.get("answers", {})
    subdirectory = (
        answers_settings.get("subdirectory", "")
        if isinstance(answers_settings, dict)
        else ""
    )
    if isinstance(subdirectory, str) and subdirectory.strip():
        folder = screenshot_folder / subdirectory

        folder.mkdir(parents=True, exist_ok=True)

    return folder

def add_frame_to_pdf(path: Path | str, frame):
    path = Path(path)

    image = Image.fromarray(frame)

    # Save the frame as PNG without changing its resolution
    png_buffer = io.BytesIO()
    image.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    # Convert PNG directly into a PDF page
    new_page_pdf = img2pdf.convert(png_buffer.getvalue())

    new_page_reader = PdfReader(io.BytesIO(new_page_pdf))

    writer = PdfWriter()

    if path.exists():
        reader = PdfReader(path)

        for page in reader.pages:
            writer.add_page(page)

    writer.add_page(new_page_reader.pages[0])

    with open(path, "wb") as f:
        writer.write(f)


def ensure_openai_api_key():
    """Load an existing key or prompt the user to copy/type one."""
    from dotenv import dotenv_values, load_dotenv, set_key
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QLabel,
        QLineEdit,
        QVBoxLayout,
    )
    import webbrowser

    env_file = APP_DIR / ".env"

    def is_api_key(value):
        return bool(re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", value.strip()))

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not is_api_key(key) and env_file.exists():
        key = (dotenv_values(env_file).get("OPENAI_API_KEY") or "").strip()

    if is_api_key(key):
        os.environ["OPENAI_API_KEY"] = key
        load_dotenv(env_file, override=False)
        return
    key = ""

    clipboard = app.clipboard()
    key = clipboard.text().strip()
    if not is_api_key(key):
        key = ""

    dialog = QDialog()
    dialog.setWindowTitle("OpenAI API key")
    dialog.setMinimumWidth(430)
    layout = QVBoxLayout(dialog)
    message = QLabel(
        "Copy an OpenAI API key to save it automatically, or type it below."
    )
    message.setWordWrap(True)
    layout.addWidget(message)

    key_input = QLineEdit()
    key_input.setEchoMode(QLineEdit.EchoMode.Password)
    key_input.setPlaceholderText("sk-...")
    layout.addWidget(key_input)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save
        | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if key:
        key_input.setText(key)
        dialog.accept()
    else:
        timer = QTimer(dialog)

        def check_clipboard():
            copied_key = clipboard.text().strip()
            if is_api_key(copied_key):
                key_input.setText(copied_key)
                dialog.accept()

        timer.timeout.connect(check_clipboard)
        timer.start(300)
        webbrowser.open("https://platform.openai.com/api-keys")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        timer.stop()
        key = key_input.text().strip()

    while not is_api_key(key):
        message.setText("That does not look like an API key. Please try again.")
        key_input.clear()
        timer = QTimer(dialog)

        def check_clipboard_again():
            copied_key = clipboard.text().strip()
            if is_api_key(copied_key):
                key_input.setText(copied_key)
                dialog.accept()

        timer.timeout.connect(check_clipboard_again)
        timer.start(300)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        timer.stop()
        key = key_input.text().strip()

    set_key(str(env_file), "OPENAI_API_KEY", key, quote_mode="always")
    os.environ["OPENAI_API_KEY"] = key


printStatus("Checking OpenAI API key...")
ensure_openai_api_key()

printStatus("Loading GPT...")
import gpt


printStatus("Loading DXCam...")
import dxcam


printStatus("Loading keyboard...")
import keyboard


printStatus("Loading mouse...")
from pynput import mouse


printStatus("Loading Qt...")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer


printStatus("Loading PaddleOCR...")
from paddleocr import PaddleOCR


# ============================================================
# Initialize camera
# ============================================================

printStatus("Initializing camera...")

camera = dxcam.create(
    output_color="RGB"
)


capture_region = (
    int(geometry.left() * dpr),
    int(geometry.top() * dpr),
    int((geometry.left() + geometry.width()) * dpr),
    int((geometry.top() + geometry.height()) * dpr),
)

print("Capture region:", capture_region)
print("DPR:", dpr)


# ============================================================
# Initialize OCR
# ============================================================

printStatus("Initializing OCR...")

OCR_SETTINGS = SETTINGS["ocr"]
ocr_language = OCR_SETTINGS["language"]
ocr_device = OCR_SETTINGS["device"]
ocr_min_confidence = max(0.0, min(1.0, float(OCR_SETTINGS["min_confidence"])))
ocr_region_gap = OCR_SETTINGS["region_gap"]
ocr_region_padding = OCR_SETTINGS["region_padding"]
ignored_text = {
    text.strip()
    for text in OCR_SETTINGS["ignored_text"]
    if isinstance(text, str) and text.strip()
}

ocr = PaddleOCR(
    lang=ocr_language,
    device=ocr_device,
    use_doc_orientation_classify=OCR_SETTINGS["use_doc_orientation_classify"],
    use_doc_unwarping=OCR_SETTINGS["use_doc_unwarping"],
    use_textline_orientation=OCR_SETTINGS["use_textline_orientation"],
)


# ============================================================
# Overlay enabled state
# ============================================================

overlay_enabled = True


# ============================================================
# Keyboard request flags
#
# Keyboard callbacks run outside the Qt main thread.
# They ONLY set flags.
#
# Qt checks these flags and performs the actual work.
# ============================================================

screenshot_requested = False
screenshot_image_requested = False

home_requested = False
delete_requested = False
insert_requested = False
escape_requested = False

REASONING_SETTINGS = SETTINGS["reasoning"]
configured_efforts = REASONING_SETTINGS["efforts"]
efforts = list(dict.fromkeys(
    effort
    for effort in configured_efforts
    if isinstance(effort, str) and effort.strip()
))
if not efforts:
    efforts = [REASONING_SETTINGS["default"]]

default_effort = REASONING_SETTINGS["default"]
last_used_effort = REASONING_SETTINGS["last_used"]
starting_effort = (
    last_used_effort
    if last_used_effort in efforts
    else default_effort
)
effort_index = efforts.index(starting_effort) if starting_effort in efforts else 0
window.update_instructions(efforts[effort_index])

HOTKEYS = SETTINGS["hotkeys"]
effort_colors = SETTINGS["effort_colors"]


# ============================================================
# Background job system
#
# OCR + GPT can take several seconds.
# They must NOT run on the Qt main thread.
# ============================================================

job_queue = queue.Queue()
result_queue = queue.Queue()

job_running = False


def set_answer(txt):
    overlay.set_answer(
        txt,
        effort_colors[efforts[effort_index]]
    )

def load_title_cache():
    cache = load_settings()["title_cache"]
    return {
        title: info
        for title, info in cache.items()
        if isinstance(title, str) and isinstance(info, dict)
    }

def save_title_cache(title_cache):
    try:
        update_settings({"title_cache": title_cache})

    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to save title cache: {e}")


def load_test_info_override():
    """Load non-empty manual course/test fields from the shared settings file."""
    settings = load_settings()
    test_info = settings["test_info"]

    return {
        key: value.strip()
        for key, value in test_info.items()
        if key in {"course", "test_name", "short_test_name"}
        and isinstance(value, str)
        and value.strip()
    }


title_cache = load_title_cache()


def background_worker():
    """
    Runs OCR/GPT jobs away from the Qt main thread.
    """

    while True:

        job = job_queue.get()

        if job is None:
            break

        frame, include_image = job

        try:

            print()
            print("========================================")
            print("BACKGROUND OCR JOB")
            print("========================================")

            # ------------------------------------------------
            # OCR
            # ------------------------------------------------

            boxes, ocr_results, start_x, end_x = run_ocr(frame)

            # ------------------------------------------------
            # Keep only OCR inside the detected question region
            # ------------------------------------------------

            if start_x is not None and end_x is not None:

                filtered_boxes = []
                filtered_ocr_results = []

                for box, text in zip(boxes, ocr_results):

                    x1, _, x2, _ = box

                    # Keep text whose box overlaps the question region
                    if x2 >= start_x and x1 <= end_x:

                        filtered_boxes.append(box)
                        filtered_ocr_results.append(text)

                boxes = filtered_boxes
                ocr_results = filtered_ocr_results

                cropped_frame = frame[:, start_x:end_x]

            else:

                cropped_frame = frame

            print("OCR complete.")
            print("Detected in question region:", len(ocr_results))

            # ------------------------------------------------
            # Title / cache
            # ------------------------------------------------

            set_answer("# Analyzing...")

            title = get_window_title()
            cached_test_info = title_cache.get(title)
            manual_test_info = load_test_info_override()
            test_info = {
                **(cached_test_info or {}),
                **manual_test_info,
            }

            required_test_info = ("course", "test_name", "short_test_name")
            has_complete_test_info = all(
                test_info.get(key) for key in required_test_info
            )

            if has_complete_test_info:
                print("Using configured or cached test info.")
                title_for_gpt = None

            else:
                print("Extracting missing test info from window title...")
                title_for_gpt = title

            # ------------------------------------------------
            # GPT
            # ------------------------------------------------

            if include_image:

                print("Sending OCR + screenshot to GPT...")

                response = gpt.answer(
                    ocr_results,
                    title=title_for_gpt,
                    image=cropped_frame,
                    effort=efforts[effort_index],
                )

            else:

                print("Sending OCR to GPT...")

                response = gpt.answer(
                    ocr_results,
                    title=title_for_gpt,
                    effort=efforts[effort_index],
                )

            print("GPT response received.")

            # ------------------------------------------------
            # Test info
            # ------------------------------------------------

            generated_test_info = response.get("test_info") or {}
            combined_test_info = {
                **generated_test_info,
                **(cached_test_info or {}),
                **manual_test_info,
            }
            test_info = (
                combined_test_info
                if all(combined_test_info.get(key) for key in required_test_info)
                else None
            )

            if (
                test_info is not None
                and title is not None
                and not manual_test_info
                and cached_test_info is None
            ):
                title_cache[title] = test_info
                save_title_cache(title_cache)
                print("Test info cached and saved.")

            response["test_info"] = test_info

            # ------------------------------------------------
            # Queue result
            # ------------------------------------------------

            result_queue.put(
                (
                    "success",
                    response,
                    boxes,
                    ocr_results,
                    cropped_frame,
                )
            )

        except Exception as e:

            print()
            print("========================================")
            print("BACKGROUND JOB ERROR")
            print("========================================")
            print(repr(e))
            print("========================================")

            result_queue.put(
                (
                    "error",
                    repr(e),
                    None,
                    None,
                )
            )

        finally:

            job_queue.task_done()

worker_thread = threading.Thread(
    target=background_worker,
    daemon=True,
)

worker_thread.start()


# ============================================================
# OCR
# ============================================================

def run_ocr(frame):

    result = ocr.predict(frame)

    boxes = []
    ocr_results = []

    for res in result:

        texts = res["rec_texts"]
        scores = res["rec_scores"]
        detected_boxes = res["rec_boxes"]

        for text, score, box in zip(
            texts,
            scores,
            detected_boxes,
        ):

            if score < ocr_min_confidence:
                continue

            text = text.strip()

            if text in ignored_text:
                continue

            box = [int(x) for x in box]

            boxes.append(box)
            ocr_results.append(text)

    print(f"Detected {len(ocr_results)} OCR results")

    if not boxes:
        return boxes, ocr_results, None, None

    # Find main horizontal text region

    intervals = []

    for box in boxes:

        x1, _, x2, _ = box

        intervals.append(
            (x1, x2)
        )

    intervals.sort()

    groups = []
    current_group = [intervals[0]]

    gap = ocr_region_gap

    for interval in intervals[1:]:

        current_end = max(
            x2
            for _, x2 in current_group
        )

        next_start = interval[0]

        if next_start - current_end <= gap:

            current_group.append(interval)

        else:

            groups.append(current_group)
            current_group = [interval]

    groups.append(current_group)

    main_group = max(
        groups,
        key=len
    )

    start_x = min(
        x1
        for x1, _ in main_group
    )

    end_x = max(
        x2
        for _, x2 in main_group
    )

    # Use "Question ##" as the left boundary

    question_boxes = [
        box
        for text, box in zip(
            ocr_results,
            boxes,
        )
        if re.search(
            r"\bQuestion\s+\d+\b",
            text,
            re.IGNORECASE,
        )
    ]

    if question_boxes:

        start_x = min(
            box[0]
            for box in question_boxes
        )

    # Use "## pts" as the right boundary

    points_boxes = [
        box
        for text, box in zip(
            ocr_results,
            boxes,
        )
        if re.search(
            r"\b\d+\s*pts\b",
            text,
            re.IGNORECASE,
        )
    ]

    if points_boxes:

        end_x = max(
            box[2]
            for box in points_boxes
        )

    # Add padding

    padding = ocr_region_padding

    start_x = max(
        0,
        start_x - padding
    )

    end_x = min(
        frame.shape[1],
        end_x + padding
    )

    return (
        boxes,
        ocr_results,
        start_x,
        end_x,
    )


# ============================================================
# Process GPT response
#
# IMPORTANT:
# This is called by the Qt main thread.
# ============================================================

def process_response(
    response,
    boxes,
    ocr_results,
    frame,
):

    formatted_response: str = response["response"]

    set_answer(formatted_response)

    answers = response["answers"]

    path = screenshot_folder

    test_name = "answers"
    short_test_name = "answers"

    if response.get("test_info", None):

        test_info = response["test_info"]

        course = test_info["course"]

        test_name = test_info["test_name"]
        short_test_name = test_info["short_test_name"]
        short_test_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', short_test_name).strip().rstrip('.')
        path = (path / course)

    if SAVE_MARKDOWN or SAVE_PDF:
        path.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Markdown
    # --------------------------------------------------------

    if SAVE_MARKDOWN:
        with open(
            path / f"{short_test_name}.md",
            "a+",
            encoding="utf-8",
        ) as f:

            f.seek(0)

            txt = f.read()

            datenow = datetime.now()

            date = "## " + datenow.strftime(
                "%B %d, %Y"
            )

            time = (
                f"<br><small>"
                f"{datenow.strftime('%I:%M %p')}"
                f"</small>"
            )

            formatted_title = f"# {test_name}"

            if formatted_title not in txt:

                if txt:

                    if txt.endswith("\n\n"):
                        pass

                    elif txt.endswith("\n"):
                        f.write("\n")

                    else:
                        f.write("\n\n")

                f.write(
                    formatted_title
                    + "\n\n"
                )

            if date not in txt:

                f.write(
                    date
                    + "\n"
                )

            if time not in txt:

                f.write(
                    "\n"
                    + time
                    + "\n"
                )

            md_answer = re.sub(
                r"^(#+)",
                r"#\1",
                formatted_response,
                flags=re.MULTILINE,
            )

            f.write(
                md_answer
                + "\n"
            )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if SAVE_PDF:
        pdf_path = path / f"{short_test_name}.pdf"

        add_frame_to_pdf(
            pdf_path,
            frame,
        )

    # --------------------------------------------------------
    # Highlight boxes
    # --------------------------------------------------------

    output_boxes = []

    for answer in answers:

        index = answer["target_index"]

        if not (
            0 <= index < len(boxes)
        ):

            print(
                f"Invalid target index from GPT: {index}"
            )

            continue

        box = boxes[index]

        output_boxes.append(
            [
                int(box[0] / dpr),
                int(box[1] / dpr),
                int(box[2] / dpr),
                int(box[3] / dpr),
            ]
        )

    print(
        f"Highlighting {len(output_boxes)} boxes"
    )

    overlay.set_boxes(
        output_boxes
    )


# ============================================================
# Start screenshot job
#
# This function runs on the Qt main thread.
#
# It captures the frame quickly, then gives the expensive
# OCR/GPT work to the background worker.
# ============================================================

def start_screenshot_job(
    include_image=False
):

    global job_running

    if not overlay_enabled:

        print(
            "Screenshot ignored: overlay is disabled"
        )

        return

    if job_running:

        print(
            "Screenshot ignored: another OCR job is already running."
        )

        return

    print()
    print("========================================")

    if include_image:

        print("Screenshot + Image")

    else:

        print("OCR Screenshot")

    print("========================================")

    # --------------------------------------------------------
    # Capture happens here.
    # This is quick compared with OCR/GPT.
    # --------------------------------------------------------

    set_answer("# Capturing...")

    frame = camera.grab(
        region=capture_region
    )

    if frame is None:

        print("Capture failed")

        overlay.set_answer(
            "# Capture failed",
            "red",
        )

        return

    # --------------------------------------------------------
    # Send the expensive part to the worker.
    # --------------------------------------------------------

    job_running = True

    job_queue.put(
        (
            frame,
            include_image,
        )
    )


# ============================================================
# Home - Configuration mode
# ============================================================

def home_pressed():

    global home_requested

    home_requested = True


keyboard.add_hotkey(
    HOTKEYS["configuration"],
    home_pressed,
    suppress=True,
)


# ============================================================
# Delete - Exit program
# ============================================================

def delete_pressed():

    global delete_requested

    delete_requested = True


keyboard.add_hotkey(
    HOTKEYS["exit"],
    delete_pressed,
    suppress=True,
)


# ============================================================
# Insert - Enable / Disable overlay
# ============================================================

def insert_pressed():

    global insert_requested

    insert_requested = True


keyboard.add_hotkey(
    HOTKEYS["toggle_overlay"],
    insert_pressed,
    suppress=True,
)


# ============================================================
# Escape - Clear boxes and answer
# ============================================================

def escape_pressed():

    global escape_requested

    escape_requested = True


keyboard.add_hotkey(
    HOTKEYS["clear_answer"],
    escape_pressed,
    suppress=True,
)


# ============================================================
# F10
#
# IMPORTANT:
# Do NOT run OCR/GPT here.
# Just tell Qt that F10 was pressed.
# ============================================================

def f10_pressed():

    global screenshot_image_requested

    if not overlay_enabled:

        print(
            "F10 ignored: overlay is disabled"
        )

        return

    print("F10 PRESSED")

    screenshot_image_requested = True


keyboard.add_hotkey(
    HOTKEYS["image_capture"],
    f10_pressed,
    suppress=True,
)


# ============================================================
# Backtick
# ============================================================

def backtick_pressed():

    global screenshot_requested

    if not overlay_enabled:

        print(
            "Backtick ignored: overlay is disabled"
        )

        return

    print("BACKTICK PRESSED")

    screenshot_requested = True


keyboard.add_hotkey(
    HOTKEYS["ocr_capture"],
    backtick_pressed,
    suppress=True,
)


# ============================================================
# Reasoning effort
# ============================================================

efforts_len = len(efforts)


def change_effort():

    print("RIGHT CLICK")

    global effort_index

    effort_index += 1

    if effort_index >= efforts_len:
        effort_index = 0

    current_effort = efforts[effort_index]

    try:
        update_settings({"reasoning": {"last_used": current_effort}})
    except (OSError, TypeError) as e:
        print(f"Failed to save reasoning effort: {e}")

    window.update_instructions(current_effort)

    set_answer(
        f"# Reasoning Effort: **{current_effort}**"
    )


keyboard.add_hotkey(
    HOTKEYS["cycle_effort"],
    change_effort,
    suppress=True,
)


# ============================================================
# Mouse
# ============================================================

mouse_click_requested = None


def mouse_clicked(
    x,
    y,
    button,
    pressed,
):

    global mouse_click_requested

    if pressed and button == mouse.Button.left:

        mouse_click_requested = (
            x,
            y,
        )


# ============================================================
# Process background results
#
# Runs on Qt main thread.
# ============================================================

def check_background_results():

    global job_running

    try:

        while True:

            result = result_queue.get_nowait()

            result_type = result[0]

            # ------------------------------------------------
            # Successful OCR/GPT job
            # ------------------------------------------------

            if result_type == "success":

                (
                    _,
                    response,
                    boxes,
                    ocr_results,
                    cropped_frame,
                ) = result

                job_running = False

                print(
                    "Processing GPT response..."
                )

                process_response(
                    response,
                    boxes,
                    ocr_results,
                    cropped_frame,
                )

            # ------------------------------------------------
            # Failed OCR/GPT job
            # ------------------------------------------------

            elif result_type == "error":

                (
                    _,
                    error,
                    _,
                    _,
                ) = result

                job_running = False

                print()
                print("OCR/GPT ERROR:")
                print(error)

                overlay.set_answer(
                    "# Error\n"
                    + str(error)
                )

            result_queue.task_done()

    except queue.Empty:

        pass


# ============================================================
# Keyboard / mouse polling
#
# Runs on the Qt main thread.
# ============================================================

def check_keyboard():

    global screenshot_requested
    global screenshot_image_requested

    global home_requested
    global delete_requested
    global insert_requested
    global escape_requested

    global overlay_enabled

    global mouse_click_requested

    # ========================================================
    # Check background OCR/GPT results first
    # ========================================================

    check_background_results()

    # ========================================================
    # Escape
    # ========================================================

    if escape_requested:

        escape_requested = False

        print("ESC PRESSED")

        overlay.set_boxes([])
        overlay.set_answer()

    # ========================================================
    # Home
    # ========================================================

    if home_requested:

        home_requested = False

        print()
        print("========================================")
        print("HOME PRESSED")
        print("Configuration mode")
        print("========================================")

        overlay.show()
        overlay.set_click_through(False)

    # ========================================================
    # Delete
    # ========================================================

    if delete_requested:

        delete_requested = False

        print()
        print("========================================")
        print("DELETE PRESSED")
        print("Exiting program...")
        print("========================================")

        QApplication.quit()

        return

    # ========================================================
    # Insert
    # ========================================================

    if insert_requested:

        insert_requested = False

        overlay_enabled = not overlay_enabled

        print()
        print("========================================")
        print("INSERT PRESSED")
        print(
            "Overlay:",
            "ENABLED"
            if overlay_enabled
            else "DISABLED",
        )
        print("========================================")

        if overlay_enabled:

            overlay.show()

        else:

            overlay.hide()

    # ========================================================
    # F10
    #
    # Start screenshot + image job.
    # ========================================================

    if screenshot_image_requested:

        screenshot_image_requested = False

        if overlay_enabled:

            start_screenshot_job(
                include_image=True
            )

    # ========================================================
    # Backtick
    #
    # Start OCR-only job.
    # ========================================================

    if screenshot_requested:

        screenshot_requested = False

        if overlay_enabled:

            start_screenshot_job(
                include_image=False
            )

    # ========================================================
    # Mouse click
    # ========================================================

    if mouse_click_requested is not None:

        x, y = mouse_click_requested

        x *= dpr
        y *= dpr

        mouse_click_requested = None

        for i, box in enumerate(
            overlay.boxes
        ):

            if (
                box[0] <= x <= box[2]
                and
                box[1] <= y <= box[3]
            ):

                print(
                    "POPPING BOX",
                    i,
                )

                overlay.boxes.pop(i)

                overlay.set_boxes(
                    overlay.boxes
                )

                break


# ============================================================
# Qt timer
#
# 10 ms polling interval.
# ============================================================

timer = QTimer()

timer.timeout.connect(
    check_keyboard
)

timer.start(10)


# ============================================================
# Start Qt
# ============================================================

print("Keyboard listener started.")
print("Press ` for OCR-only screenshot.")
print("Press Home for configuration mode.")
print("Press Insert to hide/show the overlay.")
print("Press Escape to clear boxes and answer.")
print("Press Delete to exit the program.")
print("Press F10 for screenshot + image to GPT.")


def start_ready_timer():

    overlay.set_answer(
        "# Ready\n"
        + window.instructions
        + "\nYou may now drag and resize this window. "
        "Click SET when you're done."
        + f"\nReasoning Effort: "
        f"<strong><span style='color: "
        f"{effort_colors[efforts[effort_index]]}'>"
        f"{efforts[effort_index]}"
        f"</span></strong>"
    )

    overlay.show_set_button()


QTimer.singleShot(
    0,
    start_ready_timer,
)


# ============================================================
# Mouse listener
# ============================================================

mouse_listener = mouse.Listener(
    on_click=mouse_clicked
)

mouse_listener.start()


# ============================================================
# Run Qt
# ============================================================

try:

    sys.exit(
        app.exec()
    )

finally:

    print("Shutting down...")

    keyboard.unhook_all()

    mouse_listener.stop()

    os._exit(0)
