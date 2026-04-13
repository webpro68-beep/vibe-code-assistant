# AUDIO STUDIO PATCH — 2026-04-11

Bản patch này thêm một pipeline audio production-safe vào monorepo:

- voice profiles với consent bắt buộc
- upload voice sample
- ElevenLabs voice clone / TTS adapter
- breath pacing theo nhịp nghỉ tự nhiên
- music asset library / generated music
- FFmpeg audio mix
- FFmpeg mux audio vào video

## Capability chính
- `POST /api/v1/audio/voice-profiles`
- `POST /api/v1/audio/voice-profiles/{id}/samples`
- `POST /api/v1/audio/narration-jobs`
- `GET /api/v1/audio/narration-jobs/{id}`
- `POST /api/v1/audio/music-assets`
- `POST /api/v1/audio/music-assets/{id}/upload`
- `GET /api/v1/audio/music-assets`
- `POST /api/v1/audio/mix-jobs`
- `GET /api/v1/audio/mix-jobs/{id}`

## Safety boundary
Patch này chỉ nên dùng cho:
- giọng của chính người dùng
- hoặc giọng đã có ủy quyền rõ ràng

Không nên dùng để clone giọng người khác trái phép.

## ElevenLabs mapping
- Instant Voice Cloning API: `POST /v1/voices/add`
- Text to Speech API: `POST /v1/text-to-speech/{voice_id}`
- Music generation: endpoint adapter đã chuẩn bị theo ElevenLabs Music API

## Honest limits
- Voice sample upload hiện chưa có browser waveform editor
- Mixing đang dùng FFmpeg baseline `amix`; chưa có sidechain ducking nâng cao
- API route đang chạy synchronous path để dễ local dev; có thể chuyển sang Celery tasks nếu muốn scale
