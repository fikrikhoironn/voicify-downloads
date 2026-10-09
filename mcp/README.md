# Voicify MCP

The stdio MCP server in `server.py` gives Claude Desktop, Claude Code, and Codex access to recordings stored in `~/Documents/Voicify/`. If that folder does not exist but `~/Documents/Saylo/` does, Voicify uses the older library so existing recordings remain accessible. Transcription runs locally. When you ask Claude to read a transcript through MCP, that transcript text is provided to Claude.

## Claude Desktop import

Download `Voicify-MCP-0.2.7.mcpb` from the [latest release](https://github.com/fikrikhoironn/voicify-downloads/releases/latest). In Claude Desktop, open **Settings → Extensions → Advanced settings → Install Extension…** and choose the `.mcpb` file. The extension contains its own MCP server; you do not need to clone this repository or edit Claude's JSON configuration. Install the Voicify app in `/Applications` or `~/Applications` so the extension can find its bundled Whisper model. `transcribe_file` also requires FFmpeg; on Apple Silicon Macs, the extension looks in `/opt/homebrew/bin` as well as the app's resources.

In Claude Desktop chat, open **+ → Connectors** to find Voicify. The extension is local to Claude Desktop and does not install a connector for claude.ai.

## Tools

- `list_recordings`: recent app recordings and imports.
- `transcribe_file`: copy a local audio or video file into the app library and start transcription. Indonesian (`id`) is the default language. The tool returns a recording ID immediately.
- `get_transcript`: check status and read timestamped text, subtitle paths, and optional timestamped segments. Text lines use `[HH:MM:SS.mmm]` by default; pass `include_timestamps: false` to get plain text.

`transcribe_file` accepts M4A, MP3, WAV, MP4, MOV, AAC, FLAC, OGG, WebM, MKV, AIFF, WMA, and CAF when the installed FFmpeg can decode the audio. Every source is converted to mono, 16 kHz, 16-bit PCM WAV before it reaches `whisper-cli`. The exact codecs supported inside each container depend on the FFmpeg build.

Transcription runs in a separate local process. It continues if the MCP connection closes, and an unfinished job is resumed when the MCP server starts again after an interruption. Jobs share a lock so only one MCP transcription uses the model at a time.

The server looks for `ffmpeg` and `whisper-cli` in the Voicify app resources, the project `bin/` folder, Homebrew locations, then `PATH`. Set `VOICIFY_RESOURCES`, `VOICIFY_FFMPEG_PATH`, `VOICIFY_WHISPER_CLI_PATH`, or `VOICIFY_MODEL_PATH` to select explicit resources. It uses the multilingual `ggml-small.bin` model and the bundled Silero VAD model when available to skip non-speech audio.

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
