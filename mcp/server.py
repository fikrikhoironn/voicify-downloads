#!/usr/bin/env python3
"""Local stdio MCP server for Voicify. No third-party Python packages."""

import json
import os
import fcntl
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
LEGACY_LIBRARY = Path.home() / "Documents" / "Saylo"
VOICIFY_LIBRARY = Path.home() / "Documents" / "Voicify"
LIBRARY = VOICIFY_LIBRARY if VOICIFY_LIBRARY.is_dir() or not LEGACY_LIBRARY.is_dir() else LEGACY_LIBRARY
EXTENSIONS = {".mp3", ".m4a", ".wav", ".mp4", ".mov", ".aac", ".flac", ".ogg", ".webm", ".mkv", ".aiff", ".aif", ".wma", ".caf"}
LANGUAGES = {"id", "en", "auto"}
MAX_BYTES = 3 * 1024**3
WRITE_LOCK = threading.Lock()
JOBS_LOCK = threading.Lock()


def setting(name):
    return os.environ.get("VOICIFY_" + name) or os.environ.get("SAYLO_" + name) or os.environ.get("MEETING_TRANSCRIBER_" + name)


def resource_roots():
    explicit = setting("RESOURCES")
    roots = [Path(explicit)] if explicit else []
    roots.extend([
        PROJECT / "dist" / "Voicify.app" / "Contents" / "Resources",
        Path.home() / "Applications" / "Voicify.app" / "Contents" / "Resources",
        Path("/Applications/Voicify.app/Contents/Resources"),
    ])
    return roots


def executable(name):
    explicit = setting(name.upper().replace("-", "_") + "_PATH")
    candidates = [Path(explicit)] if explicit else []
    candidates.extend(root / "bin" / name for root in resource_roots())
    candidates.append(PROJECT / "bin" / name)
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return shutil.which(name)


def model_path():
    explicit = setting("MODEL_PATH")
    candidates = [Path(explicit)] if explicit else []
    candidates.extend(root / "models" / "ggml-small.bin" for root in resource_roots())
    candidates.append(PROJECT / "models" / "ggml-small.bin")
    return next((path for path in candidates if path.is_file() and path.stat().st_size > 100_000_000), None)


def metadata(folder):
    for filename in ("recording.json", "job.json"):
        path = folder / filename
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8")), filename
            except (OSError, ValueError):
                pass
    return None, None


def public_record(folder):
    data, kind = metadata(folder)
    if data is None:
        return None
    source = data.get("sourceFile") if kind == "recording.json" else "source" + Path(data.get("name", "")).suffix.lower()
    path = folder / source if source else None
    transcript = folder / "transcript.txt"
    return {
        "id": folder.name,
        "title": data.get("title") or data.get("name") or folder.name,
        "state": data.get("state") or data.get("status") or "unknown",
        "language": data.get("language", "id"),
        "source_path": str(path) if path and path.is_file() else None,
        "transcript_path": str(transcript) if transcript.is_file() else None,
        "modified_at": folder.stat().st_mtime,
    }


def timestamped_text(folder):
    path = folder / "transcript.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = []
    for segment in data.get("transcription", []):
        text = segment.get("text", "").strip()
        if not text:
            continue
        milliseconds = max(0, int(segment.get("offsets", {}).get("from", 0)))
        stamp = f"{milliseconds // 3600000:02d}:{milliseconds // 60000 % 60:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}"
        lines.append(f"[{stamp}] {text}")
    return "\n".join(lines) + ("\n" if lines else "")


def ensure_timestamped_text(folder):
    text = timestamped_text(folder)
    if text is not None:
        path = folder / "transcript.txt"
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return text


def save_record(folder, data):
    path = folder / "recording.json"
    temp = folder / "recording.json.tmp"
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def update_record(folder, **changes):
    with JOBS_LOCK:
        data, kind = metadata(folder)
        if kind != "recording.json":
            raise ValueError("This recording belongs to another transcription service.")
        data.update(changes)
        save_record(folder, data)


def launch_worker(folder):
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", folder.name],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    (folder / "mcp-worker.pid").write_text(str(process.pid), encoding="ascii")


def recover_workers():
    if not LIBRARY.is_dir():
        return
    for task in LIBRARY.glob("*/mcp-task.json"):
        folder = task.parent
        data, kind = metadata(folder)
        if kind != "recording.json" or data.get("state") in ("complete", "failed"):
            continue
        pid_file = folder / "mcp-worker.pid"
        try:
            pid = int(pid_file.read_text(encoding="ascii"))
            os.kill(pid, 0)
            continue
        except (OSError, ValueError):
            pass
        try:
            launch_worker(folder)
        except OSError as exc:
            update_record(folder, state="failed", error="Could not restart transcription: " + str(exc))


def transcribe_worker(folder):
    wav = folder / "mcp-input.wav"
    task_file = folder / "mcp-task.json"
    try:
        with (LIBRARY / ".mcp-worker.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not task_file.is_file():
                return
            task = json.loads(task_file.read_text(encoding="utf-8"))
            language = task["language"]
            terms = task.get("terms", "")
            data, _ = metadata(folder)
            if data.get("state") == "complete":
                return
            source = folder / data["sourceFile"]
            ffmpeg = executable("ffmpeg")
            whisper = executable("whisper-cli")
            model = model_path()
            if not ffmpeg or not whisper or not model:
                raise RuntimeError("Missing ffmpeg, whisper-cli, or the multilingual Whisper model. Install the app bundle or Homebrew tools.")
            update_record(folder, state="processing", progress=0, error=None)
            conversion = subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            if conversion.returncode:
                raise RuntimeError("Could not decode an audio track: " + conversion.stderr[-500:])
            command = [whisper, "-m", str(model), "-f", str(wav), "-l", language,
                       "-otxt", "-osrt", "-ovtt", "-oj", "-pp", "-of", str(folder / "transcript")]
            if terms:
                command += ["--prompt", terms]
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode:
                raise RuntimeError("Whisper failed: " + result.stderr[-600:])
            if not (folder / "transcript.txt").is_file():
                raise RuntimeError("Whisper did not produce a transcript.")
            ensure_timestamped_text(folder)
            update_record(folder, state="complete", progress=100, error=None)
    except Exception as exc:
        try:
            update_record(folder, state="failed", error=str(exc))
        except Exception:
            pass
    finally:
        wav.unlink(missing_ok=True)
        task_file.unlink(missing_ok=True)
        (folder / "mcp-worker.pid").unlink(missing_ok=True)


def list_recordings(limit=20):
    limit = max(1, min(int(limit), 100))
    if not LIBRARY.exists():
        return {"recordings": [], "library": str(LIBRARY)}
    entries = []
    for folder in LIBRARY.iterdir():
        if folder.is_dir():
            record = public_record(folder)
            if record:
                entries.append(record)
    entries.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"recordings": entries[:limit], "library": str(LIBRARY)}


def transcribe_file(path, language="id", title=None, terms=None):
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
        raise ValueError("Choose an audio or video file with a supported extension: " + ", ".join(sorted(EXTENSIONS)))
    if source.stat().st_size == 0 or source.stat().st_size > MAX_BYTES:
        raise ValueError("Recording must be between 1 byte and 3 GB.")
    if language not in LANGUAGES:
        raise ValueError("language must be id, en, or auto.")
    if not executable("ffmpeg") or not executable("whisper-cli") or not model_path():
        raise RuntimeError("ffmpeg, whisper-cli, and the multilingual Whisper model are required.")
    folder = LIBRARY / str(uuid.uuid4()).lower()
    folder.mkdir(parents=True, exist_ok=False)
    filename = "recording" + source.suffix.lower()
    try:
        shutil.copy2(source, folder / filename)
        data = {"id": folder.name, "title": (title or source.stem).strip()[:180],
                "created": time.time() - 978307200, "sourceFile": filename,
                "language": language, "state": "queued", "progress": 0, "error": None}
        save_record(folder, data)
        (folder / "mcp-task.json").write_text(json.dumps({"language": language, "terms": (terms or "")[:500]}), encoding="utf-8")
        launch_worker(folder)
        return {"id": folder.name, "state": "queued", "title": data["title"], "source_path": str(folder / filename),
                "message": "Transcription started locally. Poll get_transcript with this id."}
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def get_transcript(recording_id, include_segments=False):
    if not isinstance(recording_id, str) or not recording_id or any(char not in "0123456789abcdef-" for char in recording_id.lower()):
        raise ValueError("Invalid recording id.")
    folder = LIBRARY / recording_id
    record = public_record(folder) if folder.is_dir() else None
    if record is None:
        raise ValueError("Recording not found.")
    result = dict(record)
    transcript = folder / "transcript.txt"
    if transcript.is_file():
        text = ensure_timestamped_text(folder)
        result["text"] = (text if text is not None else transcript.read_text(encoding="utf-8")).strip()
        result["subtitle_paths"] = {extension: str(folder / ("transcript." + extension)) for extension in ("srt", "vtt") if (folder / ("transcript." + extension)).is_file()}
        if include_segments and (folder / "transcript.json").is_file():
            raw = json.loads((folder / "transcript.json").read_text(encoding="utf-8"))
            result["segments"] = [
                {"start": entry.get("offsets", {}).get("from", 0) / 1000,
                 "end": entry.get("offsets", {}).get("to", 0) / 1000,
                 "text": entry.get("text", "").strip()}
                for entry in raw.get("transcription", [])
            ]
    data, _ = metadata(folder)
    if data.get("error"):
        result["error"] = data["error"]
    return result


TOOLS = [
    {"name": "list_recordings", "description": "List recent local Voicify recordings, including imported Voice Memos, and their transcription states.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}}},
    {"name": "transcribe_file", "description": "Copy a local audio or video file into the Voicify library and start fully local transcription. Supports common FFmpeg-decodable formats such as M4A, MP3, WAV, MP4, MOV, FLAC, OGG, WebM, AIFF, AAC, CAF, and WMA. Whisper receives converted 16 kHz mono PCM WAV. Returns an id to poll.",
     "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string", "description": "Absolute path to a local recording or exported Voice Memo."}, "language": {"type": "string", "enum": ["id", "en", "auto"], "default": "id"}, "title": {"type": "string"}, "terms": {"type": "string", "description": "Optional vocabulary hint for proper nouns, up to 500 characters."}}}},
    {"name": "get_transcript", "description": "Get a recording's current state and completed transcript, with optional timestamped segments.",
     "inputSchema": {"type": "object", "required": ["recording_id"], "properties": {"recording_id": {"type": "string"}, "include_segments": {"type": "boolean", "default": False}}}},
]


def send(message):
    with WRITE_LOCK:
        sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def handle(request):
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "voicify", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "list_recordings":
                value = list_recordings(arguments.get("limit", 20))
            elif name == "transcribe_file":
                value = transcribe_file(arguments["path"], arguments.get("language", "id"), arguments.get("title"), arguments.get("terms"))
            elif name == "get_transcript":
                value = get_transcript(arguments["recording_id"], arguments.get("include_segments", False))
            else:
                raise ValueError("Unknown tool: " + str(name))
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
        except (KeyError, OSError, ValueError, RuntimeError) as exc:
            result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    else:
        send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}})
        return
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        recording_id = sys.argv[2]
        if recording_id and all(char in "0123456789abcdef-" for char in recording_id.lower()):
            transcribe_worker(LIBRARY / recording_id)
        return
    recover_workers()
    for line in sys.stdin:
        try:
            handle(json.loads(line))
        except Exception as exc:
            print("MCP request error: " + str(exc), file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
