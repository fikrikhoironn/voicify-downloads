# Voicify for macOS

Record meetings and transcribe them locally in Indonesian or English. Voicify can capture your microphone, system audio, or both, and can import existing audio or video files. Choose WAV for compatibility or M4A for smaller files. You can start another recording while a previous transcript is processing; transcriptions queue automatically. Recordings and transcripts stay on your Mac until you choose to share them.

TXT export and Copy offer text with or without `[HH:MM:SS.mmm]` timestamps. SRT, VTT, and JSON preserve their timing data.

## Download

[Download the latest Voicify DMG](https://github.com/fikrikhoironn/voicify-downloads/releases/latest)

Voicify requires an Apple Silicon Mac with macOS 15 or later. Open the DMG and drag Voicify into Applications. The app includes its own Whisper model; no account or internet connection is needed for transcription.

The app is ad-hoc signed and is not notarized. If macOS blocks the downloaded app, try opening it once, then use **System Settings → Privacy & Security → Open Anyway**. macOS asks for microphone and screen recording access when you first choose those recording sources.

This repository hosts downloadable builds only. Each release includes a SHA-256 checksum in its notes.

## MCP for Claude Code and Codex

The [Voicify MCP server](mcp/README.md) lets Claude Desktop, Claude Code, or Codex list recordings, transcribe a local file, and read completed transcripts. For Claude Desktop, download the `Voicify-MCP-0.2.7.mcpb` asset from the [latest release](https://github.com/fikrikhoironn/voicify-downloads/releases/latest) and import it from **Settings → Extensions → Advanced settings → Install Extension…**. Install the Voicify app in Applications first. The extension is optional and runs on your Mac.
