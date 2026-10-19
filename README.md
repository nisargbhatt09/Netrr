# Netrr

An assistive wearable for blind and low-vision users. A camera captures the scene, computer vision and vision-language models interpret it, and the system speaks what matters: objects and their positions, safety hazards, readable text, currency, and who is in front of you.

Netrr was co-designed with the Ahmedabad Blind People Association and won the Gujarat Gaurav Award (2024).

## Repository layout

The repository holds two things: a working prototype, and the dependency-free research core the project is moving toward.

| Path | What it is |
| --- | --- |
| `smart_glasses/` | The working prototype. Hardware abstraction, object detection, scene description, OCR, face recognition, and the voice interface. |
| `netrr/` | The research core. Pure standard library, no hardware or ML dependencies, so it runs and is tested anywhere. It grades each spoken claim by how well it is grounded, decides how to phrase it, and detects the platform. |
| `eval/` | Evaluation harness. Runs a narrator backend over a fixed frame set and writes claim-level output as JSONL, with no camera or microphone involved. |
| `frames/` | The fixed input set for the benchmark, seeded from the prototype images. |
| `results/` | Harness output (gitignored). |
| `tests/` | Unit tests for `netrr/`, platform detection, camera backend selection, and the doctor checks. |
| `scripts/` | Platform-aware install script. |
| `pyproject.toml` | Packaging: optional extras, and the `netrr` and `netrr-doctor` commands. |
| `docs/` | Hardware setup guide. |
| `archive/` | Superseded early scripts and launchers, kept for reference. |
| `RESULTS.md` | Append-only log of every experiment. |

## Features

The prototype (`smart_glasses/`) provides:

- **Object detection**: YOLOE (default) or YOLO, with 3x3 grid position ("chair at middle left") and a bounding-box based distance estimate.
- **Scene description**: Moondream first, Google Gemini as fallback.
- **Text recognition**: Google Cloud Vision for OCR, Gemini as fallback.
- **Translation**: Multi-language text translation through Gemini.
- **Currency recognition**: Notes and denominations, via Moondream or Gemini.
- **Face recognition**: Identifies known people and can learn a new face by name. Optional; it needs the `dlib` and `face_recognition` packages and is disabled cleanly when they are absent.
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

- A machine to run on: a **Raspberry Pi 4B (4 GB)**, an **NVIDIA Jetson**, or a laptop for development.
- Raspberry Pi Camera Module V2, a Jetson CSI camera, or a compatible webcam.
- Microphone and speaker or headphones (both optional, with keyboard and text fallbacks).
- Internet access for the cloud features.
- API keys: Google Gemini (required for the migrated paths), Moondream for scene analysis, and optionally Google Cloud Vision for OCR.

Software: Python 3.10+. Platform-specific dependencies are declared as optional extras in `pyproject.toml`: `.[pi]` for `picamera2`, `.[jetson]` for `jetson-stats`, and `.[face]` for `dlib` and `face_recognition`. `requirements.txt` remains for a plain `pip install -r`.

**Jetson note:** the CSI camera is read through a GStreamer pipeline (`nvarguscamerasrc`), so OpenCV must be built with GStreamer support. The JetPack system package provides this (`sudo apt install python3-opencv`); the pip wheels `opencv-python` and `opencv-python-headless` do not. The install script handles this on a Jetson by taking OpenCV and numpy from apt, creating the venv with `--system-site-packages`, and installing the project with `pip install --no-deps` so no wheel shadows the system build. `netrr-doctor` reports whether the OpenCV it finds has GStreamer.

**Face recognition note:** face identification needs `dlib` and `face_recognition`. Both are native extensions and can take a long time to build, especially on a Raspberry Pi, so the install script does not install them. Add them with `pip install -e '.[face]'` if you want that feature. Every other feature works without them, and the related voice commands respond with a clear message instead of failing.

## Installation

The quickest path is the install script, which detects the platform and installs the matching extras:

```bash
git clone https://github.com/nisargbhatt09/Netrr.git
cd Netrr
./scripts/install.sh
```

Or install manually inside a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

pip install -e .                # Raspberry Pi: pip install -e '.[pi]'
                                # Jetson:       pip install -e '.[jetson]'

cp .env.example .env            # then fill in your keys
```

Confirm the environment before running:

```bash
netrr-doctor
```

`netrr-doctor` reports the detected platform, which dependencies are present, camera and audio availability, whether the OpenCV it finds has GStreamer, and whether your API keys are set. It exits non-zero only on a hard failure.

## Running the prototype

After `pip install -e .`, the `netrr` console command is available. `python -m smart_glasses` and `python run.py` are equivalent, and all three accept the same arguments.

```bash
# Run everything (object detection, scene, text, face, voice)
netrr --mode all

# Run a single module
netrr --mode object
netrr --mode scene
netrr --mode text
netrr --mode face
netrr --mode voice

# List audio devices and exit (useful for choosing a microphone)
netrr --list-audio

# Force hardware settings, useful for testing on a laptop
netrr --mode all --mic false --speaker false

# Choose the detection model
netrr --mode object --model yoloe-11s-seg.pt

# Control logging
netrr --mode all --log-file custom.log --log-level DEBUG
```

From the repository root, `python -m smart_glasses --mode all` and `python run.py --mode all` do the same thing.

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

- `smart_glasses/main.py` is the single launcher. `run.py`, `python -m smart_glasses` and the `netrr` console command all reach it. The older `app.py` and `start.py` launchers are in `archive/`.
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