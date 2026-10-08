# Voicify MCP

The stdio MCP server in `server.py` gives Codex and Claude Code access to recordings stored in `~/Documents/Voicify/`. If that folder does not exist but `~/Documents/Saylo/` does, Voicify uses the older library so existing recordings remain accessible. It runs locally and sends no audio or transcript data to a remote service.

## Tools

- `list_recordings`: recent app recordings and imports.
- `transcribe_file`: copy a local audio or video file into the app library and start transcription. Indonesian (`id`) is the default language. The tool returns a recording ID immediately.
- `get_transcript`: check status and read timestamped text, subtitle paths, and optional timestamped segments. Text lines use `[HH:MM:SS.mmm]` by default; pass `include_timestamps: false` to get plain text.

`transcribe_file` accepts M4A, MP3, WAV, MP4, MOV, AAC, FLAC, OGG, WebM, MKV, AIFF, WMA, and CAF when the installed FFmpeg can decode the audio. Every source is converted to mono, 16 kHz, 16-bit PCM WAV before it reaches `whisper-cli`. The exact codecs supported inside each container depend on the FFmpeg build.

Transcription runs in a separate local process. It continues if the MCP connection closes, and an unfinished job is resumed when the MCP server starts again after an interruption. Jobs share a lock so only one MCP transcription uses the model at a time.

The server looks for `ffmpeg` and `whisper-cli` in the Voicify app resources, the project `bin/` folder, then `PATH`. Set `VOICIFY_RESOURCES`, `VOICIFY_FFMPEG_PATH`, `VOICIFY_WHISPER_CLI_PATH`, or `VOICIFY_MODEL_PATH` to select explicit resources. It uses the multilingual `ggml-small.bin` model.

## Codex setup

```sh
codex mcp add voicify -- /usr/bin/python3 /absolute/path/to/local-transcribe/mcp/server.py
```

## Claude Code setup

Add the server to your user configuration so it is available in every Claude Code project:

```sh
claude mcp add --scope user voicify -- /usr/bin/python3 /absolute/path/to/local-transcribe/mcp/server.py
claude mcp get voicify
```

The server must be able to find the Voicify app resources and FFmpeg as described above. In Claude Code, ask it to use the `voicify` MCP tools to list recordings, transcribe a local file, or read a transcript.

Voice Memos keeps its private recording folder behind macOS privacy controls. Export a memo from Voice Memos to a normal file, then pass that file's absolute path to `transcribe_file`. An imported memo is then visible through `list_recordings` and in the Mac app.
