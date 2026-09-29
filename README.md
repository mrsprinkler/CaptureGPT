# CaptureGPT

[![Download Latest Release](https://img.shields.io/badge/Download-Latest%20Release-2ea44f?style=for-the-badge&logo=github)](https://github.com/mrsprinkler/CaptureGPT/releases/latest)

CaptureGPT is a Windows desktop overlay that captures the area behind it, reads on-screen questions, and sends them to the OpenAI API. Use OCR text mode for lower token use, or image mode when the screenshot's visual details matter.

## Features

- **OCR-only capture:** runs PaddleOCR on the captured area and sends the extracted text to the model.
- **Screenshot + image capture:** sends both OCR text and the image. This uses more tokens than OCR-only mode.
- **Answer overlay:** displays the model's response and highlights the OCR text associated with answers.
- **Test organization:** identifies the course and test from the active window title and course list, or uses manual `test_info` from `settings.json`. It saves responses as Markdown and appends captures to a PDF under `Answers/<course>/`.
- **Reasoning effort control:** change the model's reasoning effort while the app is running.
- **Capture exclusion:** asks Windows to exclude the CaptureGPT overlay itself from screen capture and recording. This does not hide the underlying screen from recording software.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| <kbd>`</kbd> | Capture using OCR text only |
| <kbd>F10</kbd> | Capture and send the screenshot image with OCR text |
| <kbd>Home</kbd> | Enter configuration mode |
| <kbd>Insert</kbd> | Show or hide the overlay |
| <kbd>Escape</kbd> | Clear the answer and OCR boxes |
| <kbd>F9</kbd> | Change reasoning effort |
| <kbd>Delete</kbd> | Exit CaptureGPT |

Once the overlay is ready, drag and resize it over the area you want to capture, then click **SET**. The overlay area determines the capture region.

### Reasoning effort colors

The default colors are:

| Effort | Color |
| --- | --- |
| `low` | Green (`#4CAF50`) |
| `medium` | Light green (`#8BC34A`) |
| `high` | Yellow (`#FFC107`) |
| `xhigh` | Orange (`#FF9800`) |
| `max` | Red (`#F44336`) |

To change a color, edit the top-level `effort_colors` object in `settings.json`. Use CSS hex colors, keep the effort names unchanged, and restart CaptureGPT for changes to take effect:

```json
"effort_colors": {
  "low": "#4CAF50",
  "medium": "#8BC34A",
  "high": "#FFC107",
  "xhigh": "#FF9800",
  "max": "#F44336"
}
```

## Requirements

- Windows
- Python 3.11 for running from source
- An NVIDIA GPU and compatible driver for the configured PaddlePaddle GPU OCR runtime
- An OpenAI API key
- Internet access for OpenAI requests and the initial OCR model download

## Run from source

1. Clone or download this repository.
2. Run [`setup.bat`](setup.bat) to install dependencies with `uv`.
3. Run [`run.bat`](run.bat) to start the app.
4. On first launch, CaptureGPT checks for an API key in the environment, `.env`, and clipboard. If none is found, it opens the OpenAI API keys page and watches for a copied key. You can also type the key in the prompt.

The key is stored in `.env` beside the source app. Keep this file private; it is ignored by Git.

## Download a release

You do not need to build CaptureGPT from source. [Download the latest release ZIP](https://github.com/mrsprinkler/CaptureGPT/releases/latest), extract it, then run `CaptureGPT.exe` from the extracted folder. Keep the extracted files together.

## Build a standalone app

After installing dependencies with [`setup.bat`](setup.bat), run [`build.bat`](build.bat). The PyInstaller output is written to `dist/CaptureGPT/`.

This is an onedir build and includes PaddleOCR, PaddlePaddle, NVIDIA runtime binaries, and the app's dependencies. It will be large. Keep the entire `dist/CaptureGPT/` folder together when moving or distributing the app. The first run may download OCR model files to the user's model cache.

The bundled app checks for `.env` beside `CaptureGPT.exe`; if there is no key, it opens the key setup prompt. Keep `settings.json` beside `CaptureGPT.exe` so course information is available for test identification.

## Where files go

CaptureGPT uses one `settings.json` beside the executable, or beside the source files when running from source. Relative output paths are based on that same folder. It creates an `Answers` folder there by default. When it identifies the course and test, files are saved like this:

```text
Answers/
└── AP Precalculus/
    ├── Polynomial Functions Practice.md
    └── Polynomial Functions Practice.pdf
```

The Markdown file accumulates responses with dates and times. The PDF accumulates screenshots from captures. If CaptureGPT cannot identify a course and test from the active window title, it saves to `Answers/answers.md` and `Answers/answers.pdf`.

## App settings

Edit `settings.json` beside `CaptureGPT.exe` (or in the project folder when running from source). Changes are read at startup, so restart CaptureGPT after editing.

### OCR

The `ocr` object controls OCR initialization and question-region detection:

| Setting | Default | What it controls |
| --- | --- | --- |
| `language` | `en` | PaddleOCR language code |
| `device` | `gpu:0` | Paddle device, such as `gpu:0` or `cpu` |
| `min_confidence` | `0.7` | Ignore OCR detections below this score (0 to 1) |
| `region_gap` | `150` | Maximum horizontal gap, in pixels, for grouping detected text |
| `region_padding` | `20` | Pixels added around the detected question area |
| `ignored_text` | Browser/course navigation labels | Exact OCR text to omit; supplying a list replaces the defaults |

### Reasoning and image settings

- `reasoning.efforts` sets the options cycled by the effort shortcut. The default list is `high`, `xhigh`, `medium`, `low`, `max`.
- `reasoning.default` sets the starting option. The default is `high`.
- `reasoning.mode` sets the reasoning mode for answer requests. The default is `pro`; choose a mode supported by the selected answer model.
- `models.answer` sets the model used to answer captured questions. Default: `gpt-6-astra`.
- `models.title_extraction` sets the model used to infer course and test names from the active window title. Default: `gpt-5.4-nano`.
- `effort_colors` sets the display color for each effort, as described above.
- `image.jpeg_quality` sets JPEG quality for image captures, from 1 to 100. The default is `90`.

### Shortcuts

The top-level `hotkeys` object maps actions to keys recognized by the `keyboard` package:

| Setting | Default action |
| --- | --- |
| `ocr_capture` | <kbd>`</kbd> OCR-only capture |
| `image_capture` | <kbd>F10</kbd> screenshot + image capture |
| `configuration` | <kbd>Home</kbd> configuration mode |
| `toggle_overlay` | <kbd>Insert</kbd> show/hide overlay |
| `clear_answer` | <kbd>Esc</kbd> clear answer and boxes |
| `exit` | <kbd>Delete</kbd> exit |
| `cycle_effort` | <kbd>F9</kbd> change reasoning effort |

For example, set `ocr_capture` to `ctrl+shift+o` to use a key combination.

### Output

The top-level `output` object controls saved files:

- `directory` sets the output folder. Relative paths are based beside the executable or source folder. Default: `Answers`.
- `save_markdown` enables or disables the Markdown response log. Default: `true`.
- `save_pdf` enables or disables the PDF screenshot log. Default: `true`.

## Course and test identification

There are two ways to provide course and test information in `settings.json`:

1. **Use a course list:** Set `courses` to your course names. It can be a JSON array or one comma-separated string. CaptureGPT uses the active window title and this list to infer the course, test name, and a short name for the output files. The course list is optional, but it can help the model identify tests more accurately.

   ```json
   {
     "version": 1,
     "courses": [
       "AP Computer Science",
       "AP Precalculus",
       "English 4"
     ]
   }
   ```

2. **Set `test_info` manually:** You can omit the course list and fill in `test_info` for the current test. This avoids inferring the test details from the window title. Update these values when you move to another test.

   ```json
   {
     "version": 1,
     "test_info": {
       "course": "AP Precalculus",
       "test_name": "Polynomial Functions Practice Quiz",
       "short_test_name": "Polynomial Functions Practice"
     }
   }
   ```

   `course` determines the course folder, `test_name` is used as the document heading, and `short_test_name` becomes the Markdown and PDF filenames. Non-empty manual values take precedence over inferred or cached values; any fields left blank can still be inferred from the title.

## Data and privacy

CaptureGPT sends captured OCR text to the OpenAI API. Image mode also sends the screenshot image. It sends the active window title when it needs to identify a test; identified title information is cached in `settings.json`. Your API key is stored locally in `.env` and used for API requests. Review the screen contents and window title before capturing.
