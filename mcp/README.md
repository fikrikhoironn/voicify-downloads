# Voicify MCP

This local MCP server shares the Voicify recording library with Claude Code or Codex. It provides `list_recordings`, `transcribe_file`, and `get_transcript`. Audio and transcripts stay on your Mac.

## Install

1. Install Voicify from the [latest release](https://github.com/fikrikhoironn/voicify-downloads/releases/latest) and move the app to `/Applications`.
2. Clone this repository or download its source ZIP.
3. Install FFmpeg if it is not already on your Mac. The MCP importer needs it to decode audio and video files; the Mac app does not.
4. Register the server with your client, using the actual path to `mcp/server.py` on your Mac:

```sh
claude mcp add --scope user voicify -- /usr/bin/python3 /absolute/path/to/voicify-downloads/mcp/server.py
claude mcp get voicify
```

For Codex:

```sh
codex mcp add voicify -- /usr/bin/python3 /absolute/path/to/voicify-downloads/mcp/server.py
```

The server uses the Whisper binary and model inside `/Applications/Voicify.app`. `transcribe_file` accepts M4A, MP3, WAV, MP4, MOV, AAC, FLAC, OGG, WebM, MKV, AIFF, WMA, and CAF when FFmpeg can decode the audio. Indonesian (`id`) is the default language; English (`en`) and automatic detection (`auto`) are also supported. The tool returns a recording ID immediately; use `get_transcript` to check progress and read the result.

Voice Memos files must be exported to a normal folder before passing their paths to `transcribe_file` because macOS protects Voice Memos' private storage.
