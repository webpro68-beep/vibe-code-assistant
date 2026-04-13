# End-to-end checklist

## Boot
- [ ] `cp backend/.env.example backend/.env.dev`
- [ ] `cp frontend/.env.local.example frontend/.env.local`
- [ ] `docker compose up --build`
- [ ] `GET /healthz` returns ok
- [ ] Flower opens on port 5555
- [ ] Frontend opens on port 3000

## Preview-first flow
- [ ] Upload `.txt` script on `/script-upload`
- [ ] Upload `.docx` script on `/script-upload`
- [ ] Preview payload returns scenes + subtitle segments
- [ ] Edit scene title/text inline
- [ ] Validate preview shows field-level errors when invalid
- [ ] Rebuild subtitles works
- [ ] Recalculate durations works
- [ ] Confirm create project stores `storage/projects/<project_id>`

## Render pipeline
- [ ] Build provider payload preview for Veo
- [ ] Build provider payload preview for Runway
- [ ] Build provider payload preview for Kling
- [ ] Create render job from planned scenes
- [ ] Worker dispatch step sets provider task identifiers
- [ ] Poll fallback re-enqueues unfinished scenes
- [ ] Callback endpoint accepts provider event payload
- [ ] Successful scenes upload to object storage / signed URL path
- [ ] Postprocess merges scene clips
- [ ] Subtitle burn path writes SRT / burned output when enabled
- [ ] Final status API exposes final video URL and scene states
- [ ] Frontend render job page reaches terminal state and shows preview video

## Failure handling
- [ ] Invalid file type returns 400
- [ ] Oversized upload returns 400/413
- [ ] Missing provider credentials still allows mock/scaffold path without crashing boot
- [ ] Failed scene transitions surface `error_message`
- [ ] Stuck job recovery worker task is registered in Celery beat
