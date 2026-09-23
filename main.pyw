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

SETTINGS_FILE = Path.cwd() / "settings.json"

screenshot_folder = Path.cwd() / "Answers"
screenshot_folder.mkdir(parents=True, exist_ok=True)


def get_answers_folder():
    folder = screenshot_folder

    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)

        if settings.get("answers", {}).get("subdirectory", "").strip():
            folder = (
                screenshot_folder
                / settings["answers"]["subdirectory"]
            )

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

ocr = PaddleOCR(
    lang="en",
    device="gpu:0",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
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

effort_index = 0

efforts = [
    "high",
    "xhigh",
    "medium",
    "low",
    "max",
]

effort_colors = {
    "low": "#4CAF50",
    "medium": "#8BC34A",
    "high": "#FFC107",
    "xhigh": "#FF9800",
    "max": "#F44336",
}


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

title_cache = {}

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
            test_info = title_cache.get(title)

            if test_info is not None:
                print("Using cached test info.")
                title_for_gpt = None
            else:
                print("No cached test info. Extracting title...")
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

            if test_info is None:

                test_info = response.get("test_info")

                if test_info is not None and title is not None:
                    title_cache[title] = test_info
                    print("Test info cached.")

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

    IGNORE_TEXT = {
        "Home",
        "IgniteAI Search",
        "Syllabus",
        "Modules",
        "Announcements",
        "Assignments",
        "Grades",
        "Lucid (Whiteboard)",
        "Notebook",
        "Account",
        "Dashboard",
        "Courses",
        "Calendar",
        "Inbox",
        "History",
        "Studio",
        "Help",
    }

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

            if score < 0.7:
                continue

            text = text.strip()

            if text in IGNORE_TEXT:
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

    GAP = 150

    for interval in intervals[1:]:

        current_end = max(
            x2
            for _, x2 in current_group
        )

        next_start = interval[0]

        if next_start - current_end <= GAP:

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

    padding = 20

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

    path = Path("Answers")

    test_name = "answers"
    short_test_name = "answers"

    if response.get("test_info", None):

        test_info = response["test_info"]

        course = test_info["course"]

        test_name = test_info["test_name"]
        short_test_name = test_info["short_test_name"]
        short_test_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', short_test_name).strip().rstrip('.')
        path = (path / course)

    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Markdown
    # --------------------------------------------------------

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

    pdf_path = (
        path
        / f"{short_test_name}.pdf"
    )

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
    "home",
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
    "delete",
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
    "insert",
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
    "esc",
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
    "f10",
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
    "`",
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

    set_answer(
        f"# Reasoning Effort: **{efforts[effort_index]}**"
    )


keyboard.add_hotkey(
    "f9",
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