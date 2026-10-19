# smart_glasses

The working prototype for Netrr: hardware abstraction, object detection, scene description, OCR, face recognition, and the voice interface.

This package is the runnable system. The dependency-free research core lives in `../netrr/`. For full setup, configuration, and usage, see the [root README](../README.md).

## Running

There is no `__main__.py` in this package, so run it through the repository entry point:

```bash
python run.py --mode all
```

## Modules

| Module | Class | Purpose |
| --- | --- | --- |
| `base.py` | `SmartGlasses` | Shared base: camera, audio, TTS, model loading, grid position. |
| `object_detection.py` | `ObjectDetector` | YOLOE/YOLO detection, grid position, distance estimate, hazard checks. |
| `scene_analyzer.py` | `SceneAnalyzer` | Scene description, colour, and currency (Moondream, Gemini fallback). |
| `text_recognition.py` | `TextReader` | OCR and translation (Google Cloud Vision, Gemini fallback). |
| `face_recognition.py` | `FaceRecognizer` | Face identification and enrolment. |
| `voice_assistant.py` | `VoiceAssistant` | Wake words, commands, and conversation mode. |
| `performance_monitor.py` | `PerformanceMonitor` | CPU, memory, and temperature sampling. |

## Models

- `yoloe-11s-seg.pt` (default), `yoloe-11l-seg.pt`, or `yolov11n.pt` for detection.
- Vision-language work goes to Moondream and Google Gemini. No large model runs on the device.

## License

MIT. See the [LICENSE](../LICENSE).