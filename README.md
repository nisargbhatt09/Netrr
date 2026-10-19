# Netrr

An assistive wearable for blind and low-vision users. A camera captures the scene, computer vision and vision-language models interpret it, and the system speaks what matters: objects and their positions, safety hazards, readable text, currency, and who is in front of you.

Netrr was co-designed with the Ahmedabad Blind People Association and won the Gujarat Gaurav Award (2024).

## Repository layout

The repository holds two things: a working prototype, and the dependency-free research core the project is moving toward.

| Path | What it is |
| --- | --- |
| `smart_glasses/` | The working prototype. Hardware abstraction, object detection, scene description, OCR, face recognition, and the voice interface. |
| `netrr/` | The research core. Pure standard library, no hardware or ML dependencies, so it runs and is tested anywhere. It grades each spoken claim by how well it is grounded and decides how to phrase it. |
| `eval/` | Evaluation harness. Runs a narrator backend over a fixed frame set and writes claim-level output as JSONL, with no camera or microphone involved. |
| `frames/` | The fixed input set for the benchmark, seeded from the prototype images. |
| `results/` | Harness output (gitignored). |
| `tests/` | Unit tests for `netrr/`. |
| `docs/` | Hardware setup guide. |
| `archive/` | Superseded early scripts, kept for reference. |
| `RESULTS.md` | Append-only log of every experiment. |

## Features

The prototype (`smart_glasses/`) provides:

- **Object detection**: YOLOE (default) or YOLO, with 3x3 grid position ("chair at middle left") and a bounding-box based distance estimate.
- **Scene description**: Moondream first, Google Gemini as fallback.
- **Text recognition**: Google Cloud Vision for OCR, Gemini as fallback.
- **Translation**: Multi-language text translation through Gemini.
- **Currency recognition**: Notes and denominations, via Moondream or Gemini.
- **Face recognition**: Identifies known people and can learn a new face by name.
- **Colour identification**: Names the dominant colour in view.
- **Voice interface**: Wake-word commands ("hey glasses, ...") with a full keyboard fallback when no microphone is present.
- **Conversation mode**: Natural back-and-forth through Gemini.
- **Hardware adaptability**: Detects which camera, microphone, and speaker are present and degrades gracefully when any is missing.

## Research direction: calibrated narration

A wearable that describes a scene in fluent speech gives the user no way to check it. As the field has framed the problem, that is a *verification disability*: the user cannot see the frame, so they are compelled to rely on the description, including when it is wrong.

The direction this project is taking is to make the system say how well it knows each thing it says. Every spoken statement becomes a `Claim` with a grounding grade (`supported`, `uncertain`, `unsupported`) and a harm label (`dangerous`, `inconvenient`, `cosmetic`). The grade drives how the claim is spoken:

| Grade | Harm | Action |
| --- | --- | --- |
| supported | any | state it plainly |
| uncertain | cosmetic / inconvenient | hedge ("there may be") |
| uncertain | dangerous | hedge and re-confirm on the next frame |
| unsupported | cosmetic | stay silent |
| unsupported | dangerous | stay silent and ask the user to retake the frame |

`netrr/ground/claims.py` implements this vocabulary, the cheap grading rules (presence from detections, spatial from grid position), and the policy above. It is unit-tested and has no heavy dependencies.

Status, stated plainly: the research core is implemented and tested, but it is not yet wired into the live voice pipeline, and no benchmark numbers are published. The next steps are annotating the benchmark and connecting the policy to the narrator. Nothing here should be read as a result yet.

## Requirements

- A machine to run on. The prototype targets a **Raspberry Pi 4B (4 GB)**; it also runs on a laptop for development.
- Raspberry Pi Camera Module V2 or a compatible webcam.
- Microphone and speaker or headphones (both optional, with keyboard and text fallbacks).
- Internet access for the cloud features.
- API keys: Google Gemini (required for the migrated paths), Moondream for scene analysis, and optionally Google Cloud Vision for OCR.

Software: Python 3.10+, and the packages in `requirements.txt`. Some are Raspberry Pi only (`picamera2`, `dlib`, `face_recognition`) and have no wheels on other platforms; they are commented out in `requirements.txt` and should be installed on the target device.

## Installation

```bash
# Clone the repository
git clone https://github.com/nisargbhatt09/Netrr.git
cd Netrr

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and fill in your keys
```

There is no packaging file in this repository, so install with `pip install -r requirements.txt` rather than `pip install -e .`.

## Running the prototype

`run.py` is the entry point. It passes its arguments straight through to the CLI.

```bash
# Run everything (object detection, scene, text, face, voice)
python run.py --mode all

# Run a single module
python run.py --mode object
python run.py --mode scene
python run.py --mode text
python run.py --mode face
python run.py --mode voice

# Force hardware settings, useful for testing on a laptop
python run.py --mode all --mic false --speaker false

# Choose the detection model
python run.py --mode object --model yoloe-11s-seg.pt

# Control logging
python run.py --mode all --log-file custom.log --log-level DEBUG
```

### Keyboard commands

When no microphone is available, or if you prefer typing, use the console prompt:

| Key | Action |
| --- | --- |
| `d` | Describe the scene |
| `r` | Read text |
| `t` | Translate text |
| `w` | Identify a person |
| `c` | Identify colour |
| `m` | Identify currency |
| `conv` | Start conversation mode |
| `exit` | Leave conversation mode |
| `h` | Help |
| `q` | Quit |

### Voice commands

Say a wake word ("hey glasses", "okay glasses") followed by a command: "describe", "read", "translate to Spanish", "who is this", "remember John", "what color is this", "currency", "tell me about John", "conversation mode", "help". "Exit conversation" leaves conversation mode.

## Configuration

API keys are read from the environment (`.env` is loaded at startup):

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Google Gemini, used for scene description fallback, OCR fallback, translation, and conversation. |
| `GEMINI_MODEL` | Optional. Overrides the Gemini model id. Default `gemini-3.8-flash`. |
| `MOONDREAM_API_KEY` | Moondream, used for scene description and currency. |
| `GOOGLE_VISION_API_KEY` | Optional. Google Cloud Vision, used for OCR. |

## Evaluation harness

The harness runs a narrator backend over a fixed frame set and writes one JSONL record per frame, with no camera or speaker involved.

```bash
python eval/run.py --frames frames --backend detector --out results/claims.jsonl
```

## Tests

The `netrr/` core has no heavy dependencies, so its tests run anywhere:

```bash
python -m unittest discover -s tests -p 'test_*.py'
# or, if pytest is installed
pytest -q
```

## Performance notes

The system is designed to run within the memory budget of a Raspberry Pi 4B:

- **Cloud offload**: OCR and vision-language work goes to cloud APIs rather than running large models on the device.
- **Reduced frame size**: images are resized before processing.
- **Detection interval**: detection runs on a configurable cadence rather than every frame.
- **Caching and cooldowns**: repeated descriptions of a similar scene are suppressed.
- **Hardware adaptation**: unavailable components are replaced with fallbacks rather than failing.

Running a vision-language model fully on-device is not viable on a Pi 4B with 4 GB. A 2B model at 4-bit quantization is already around 4 GB, before the runtime overhead. Local inference would need a larger board, a Jetson-class device, or a paired phone.

## Development

- Each prototype module is a class that inherits from `SmartGlasses` in `smart_glasses/base.py`.
- The research core is deliberately dependency-free. Keep it that way so it stays testable and reviewable; put hardware and model code in `smart_glasses/`.
- Add tests under `tests/` and log every experiment in `RESULTS.md`.

## License

MIT. See the `LICENSE` file.

## Acknowledgments

- Ultralytics for YOLO and YOLOE.
- Google for the Gemini API.
- Moondream for vision-language capabilities.
- Google Cloud Vision for OCR.
- The Ahmedabad Blind People Association, co-design partners on the project.

## Contributors

- Nisarg Bhatt ([nisarg-bhatt.com](https://nisarg-bhatt.com))