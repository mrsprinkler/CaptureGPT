from openai import OpenAI
import json
import base64
import io
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

from PIL import Image


client = OpenAI()


# ============================================================
# Convert DXCam NumPy image to a base64 data URL
# ============================================================
def image_to_data_url(image):
    pil_image = Image.fromarray(image)

    buffer = io.BytesIO()

    pil_image.save(
        buffer,
        format="JPEG",
        quality=90,
        optimize=True
    )

    image_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return "data:image/jpeg;base64," + image_base64

# ============================================================
# Answer
# ============================================================
def get_test_info(title):
    started_at = time.perf_counter()
    with open("settings.json","r") as f:
        courses = json.load(f).get("courses",[])
    response = client.responses.create(
    model="gpt-5.4-nano",
    reasoning={"effort": "none"},
    input=f"""Extract Course, Test Name, and Short Test Name.

Title: {title}
Courses: {courses}

Course: Match the course list. Return only the course name. Exclude unit/lesson numbers, semester, and year.

Test Name: Return ONLY the actual test/assignment name. Remove the course, unit/lesson labels, semester/year, and browser/app name.

Short Test Name: 2-5 identifying words from the test name. Do not use verbs like Evaluate, Analyze, or Calculate.

Example:
"03 Evaluate: Week 3 Graded Assignment: Ap Statistics Sem A-Semester 1-2026/2027 — Mozilla Firefox"
→ Course: "AP Statistics"
→ Test Name: "Week 3 Graded Assignment"
→ Short Test Name: "Week 3 Graded Assignment"
""",
    text={
        "format": {
            "type": "json_schema",
            "name": "test_info",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "course": {"type": "string"},
                    "test_name": {"type": ["string", "null"]},
                    "short_test_name": {"type": ["string", "null"]}
                },
                "required": ["course", "test_name", "short_test_name"],
                "additionalProperties": False
            }
        }
    }
)
    print(f"Title request took {time.perf_counter() - started_at:.2f} seconds.")
    return json.loads(response.output_text)


def answer(ocr_results, title=None, image=None, effort="xhigh"):
    started_at = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2 if title else 1) as executor:
        answer_future = executor.submit(
            _answer_request, ocr_results, image, effort
        )
        title_future = executor.submit(get_test_info, title) if title else None
        result = answer_future.result()
        if title_future is not None:
            result["test_info"] = title_future.result()
            
    print(
            json.dumps(
                result,
                indent=4
            )
        )
    print(f"Total answer() time: {time.perf_counter() - started_at:.2f} seconds.")
    return result


def _answer_request(ocr_results, image=None, effort="xhigh"):
    started_at = time.perf_counter()
    # return {"answers":[], "response":"""## Question 1: **A**. W\n## Question 2: **B**. X\n## Question 3: **B**. X"""}

    ocr_results = [
        {
            "index": index,
            "text": text
        }
        for index, text in enumerate(ocr_results)
    ]

    ocr_text = json.dumps(
        ocr_results
    )

    content = [
        {
            "type": "input_text",
            "text": ocr_text
        }
    ]

    # ========================================================
    # Add image
    # ========================================================

    if image is not None:
        image_data_url = image_to_data_url(
            image
        )

        content.append({
            "type": "input_image",
            "image_url": image_data_url
        })

    # ========================================================
    # OpenAI request
    # ========================================================

    response = client.responses.create(
        model="gpt-6-astra",
        reasoning={
            "effort": effort,
            "mode": "pro"
        },

        instructions="""
You are a computer vision assistant. Given OCR results from a screen, answer all questions.

Return every OCR index containing a correct answer. Each answer must include:
- question_number
- target_index
- exact OCR text

Do not modify or invent OCR text.

Question numbering:
- Use the visible question number if provided.
- Otherwise, number questions sequentially starting at 1.

If an image is provided, use it together with the OCR results.

Response format:
Multiple choice:
## Question #: Letter. Answer

Multiple answer / checkboxes:
## Question #: Letter, Letter, Letter. Answers

Free response:
## Question #: Answer

For multiple choice, letters follow choice order: A = 1st, B = 2nd, C = 3rd, etc.
For multiple-answer questions, include every correct letter in choice order.

Put each question on its own line. For longer free response questions, don't bold the entire answer and put it on its own line.

Note: Each Question should start with a Header-2.

Examples:
## Question 1: **B**. 10
## Question 2: **A, C, D.** Photosynthesis requires light, water, and carbon dioxide.
## Question 3: **Austin**
## Question 4:
The water cycle is driven by solar energy, which causes water to evaporate and eventually return to Earth as precipitation.

Use Markdown for formatting when helpful.
""",

        input=[
            {
                "role": "user",
                "content": content
            }
        ],

        text={
            "format": {
                "type": "json_schema",
                "name": "ocr_targets",
                "strict": True,

                "schema": {
                    "type": "object",

                    "properties": {
                        "answers": {
                            "type": "array",

                            "items": {
                                "type": "object",

                                "properties": {
                                    "question_number": {
                                        "type": "integer"
                                    },

                                    "target_index": {
                                        "type": "integer"
                                    },

                                    "text": {
                                        "type": "string"
                                    }
                                },

                                "required": [
                                    "question_number",
                                    "target_index",
                                    "text"
                                ],

                                "additionalProperties": False
                            }
                        },

                        "response": {
                            "type": "string"
                        }

                    },

                    "required": [
                        "answers",
                        "response"
                    ],

                    "additionalProperties": False
                }
            }
        }
    )

    result = json.loads(
        response.output_text
    )

    print(f"Answer request took {time.perf_counter() - started_at:.2f} seconds.")

    return result

# ============================================================
# Test
# ============================================================
if __name__ == "__main__":
    ocr_results = [
        "Question 6",
        "What is 5+5?",
        "5",
        "10",
        "15",
        "20",
        "Question 7",
        "What is the Capital of Texas?",
        "Dallas",
        "Fortworth",
        "Austin",
        "Mckinney"
    ]

    print(
        answer(ocr_results)
    )
