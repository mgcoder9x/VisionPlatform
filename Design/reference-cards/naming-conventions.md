# Naming Conventions

## Files

- `snake_case.py` for modules.
- `PascalCase` for classes.
- `snake_case` for functions/variables.
- `UPPER_SNAKE_CASE` for constants.
- Test files: `test_<module>.py`.

## Layer-specific

| Element | Convention | Example |
|---------|-----------|---------|
| Port (interface) | `IXxx` (Protocol) | `IDataSource`, `IDetector`, `IEventSink` |
| Adapter | `<Tech>Xxx` | `CV2VideoFileSource`, `YOLOv5Detector`, `KafkaSink` |
| Domain value object | `Xxx` (frozen dataclass) | `BBox`, `Detection`, `Coord` |
| DTO (kernel) | `XxxData` or `XxxRef` | `MediaPacket`, `ShmFrameRefData` |
| Wire DTO | `XxxWire` | `InferenceRequestWire` |
| Use case | `<Verb>XxxUseCase` | `ProcessFrameUseCase` |
| Stage | `<Action>Stage` | `BrightnessStage`, `DarkFilterStage` |
| Decorator | `XxxDecorator<Sink/...>` | `DLQDecoratorSink`, `BufferedRetryingSink` |

## Generic guidelines

- **Verbs for use cases**: `process_X`, `transform_X`, not `XHandler`.
- **Nouns for adapters**: `CameraReader`, not `CameraReading`.
- **Avoid abbreviations**: `frame_ref` not `frm_rf`. (Except: `cfg`, `ctx`, `req`, `resp` widely understood.)
- **Domain language**: use business terms, not tech terms. `Detection` not `OutputBlob`.

## Tests

- `test_<what>_<expected>` — descriptive.
  - Good: `test_writer_returns_none_when_all_slots_busy`.
  - Bad: `test_writer_1`.
- One assertion per concept.
- Setup in fixture, not inline (when shared).

## Anti-patterns

- ❌ `Manager`, `Helper`, `Util` — meaningless.
- ❌ `Service` everywhere — what kind?
- ❌ `data`, `info`, `result` — what type?
- ❌ Generic `Result[T]` without context.

## Do

- ✅ Specific names: `RTSPSource` not `Source`.
- ✅ Layer prefix when ambiguous: `KernelMediaPacket` (rarely needed).
- ✅ Test the name reads naturally: `processor.process(packet)`.
