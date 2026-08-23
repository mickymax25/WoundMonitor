# Clipping Factory — Technical Landscape Report
*Research date: 2026-08-23. Prices as observed on that date; entries verified on official pages are marked "(official)"; the rest come from third-party comparison articles (often affiliate/SEO content — treat exact numbers as indicative and re-verify before committing).*

---

## 1. Commercial AI clipping tools (competition + possible building blocks)

| Tool | Entry pricing (2026) | API? | Notes / reputation |
|---|---|---|---|
| **OpusClip** (opus.pro) | Free $0 / Starter $15 / Pro $29 / Business custom (official) | **Business tier only**: Video Editing API, Scheduler API, and an MCP connector (official) | Market leader; "Gen-4" clip-curation model, active-speaker detection, AI B-roll, virality score. Multi-language transcription from Starter tier. Social scheduler + multi-profile posting is **Business-only**. Gotcha: cancel your sub and projects are deleted after 3 days. Publishes its own guide on clipping Twitch VODs via API. |
| **Klap** (klap.app) | Basic $14/mo (yearly) 100 clips / Pro $39 300 clips / Pro+ $94 1,000 clips (official) | Yes — API referenced in footer, pricing not public; enterprise via Discord (official) | **French company (YC-backed, hosted on OVHcloud, GDPR-positioned)** — the strongest FR story: native French transcription (~97% claimed), 52 transcription languages, AI dubbing into 29 languages. Auto-posting to TikTok/IG/LinkedIn with unlimited social accounts on all tiers. Best fit among commercial tools for a bilingual FR/EN operation. |
| **Vizard** (vizard.ai) | Free 60 credits / Creator ~$29/mo ($16.90 yearly) / Business ~$39 ($19.50 yearly) (official) | **Yes, on all paid plans — no separate API subscription.** Rate limits: Free 1 req/min, Creator 3/min, Business 10/min; API consumes plan minutes; custom deals >10k min/mo (official docs.vizard.ai) | The cheapest legitimate "clipping-as-API" building block: REST API triggers the full pipeline (viral-moment detection → clips → JSON of clip URLs). Scheduling + up to 20 social accounts on Business. Multi-language support (~40 languages incl. FR per their docs). |
| **Munch** (getmunch.com) | ~$49/mo floor, no free plan | No public API | Sells "live trend data" matching of clips to market trends; one 2026 benchmark ranked its clip-accuracy worst-in-test at the highest price. Declining reputation. |
| **Spikes Studio** | From ~$14/mo annual, free plan exists | No public API | The **Twitch/streamer specialist** — ingests streams/VODs, fast, caps processing minutes. Good reference for gaming-clip UX. |
| **Crayo** (crayo.ai) | Hobby $19 / Clipper $39 (150 clips + 120 narration min + 300 images) / $79. No free tier | No public API | Faceless-content factory (voiceovers, viral subtitle styles, "reddit story" style formats); closest commercial product to the **narration/commentary layer** — Clipper plan ≈ $0.26/clip. |
| **Clip.fm** | Little independent 2026 coverage found | — | Appears marginal in the 2026 landscape. Low priority. |
| **OpenShorts cloud** | $12/mo for 100 min, free 20 min w/ watermark (official GitHub) | REST API + **MCP server** | Open-core newcomer; same code self-hostable free (MIT). |
| Others active in 2026 | Reap, Choppity, Ssemble, Quso (ex-vidyo.ai), Submagic, VEED, Riverside "Magic Clips", Descript | Riverside/Descript: no clip API | Submagic strong on caption styles; Riverside/Descript bundle clipping with recording. |

**Reaction-style content**: none of the core clippers do a true "AI reacts" layer. Dedicated tools exist: **Revid.ai AI Reaction Video Generator** (split-screen avatar reacting with commentary + captions), **Medeo** reaction generator, and **DreamFace "Fake Stream Generator"** (fake livestream overlays, chat, viewer counts). These prove demand but are template-grade — a custom pipeline (clip + TTS persona + avatar/PNG-tuber overlay) would out-differentiate them.

**FR-language verdict**: Klap ≻ Vizard ≈ OpusClip for French; all handle FR transcription, but Klap is built by/for the French market. Whisper-class ASR underneath means FR quality is near-English everywhere.

---

## 2. Open-source / DIY building blocks

### Ingestion — yt-dlp and legal reality
- **yt-dlp** remains the universal downloader (YouTube, Twitch VODs, Kick, podcasts). The tool is legal; the *use* is governed by each platform's ToS: **YouTube's ToS prohibits downloading except via provided features** — a ToS breach is a civil/contract matter (account bans, IP blocks), not criminal, but risk rises sharply with logged-in cookies, bulk automation, and high volume — exactly a clipping factory's profile. Datacenter IPs are aggressively throttled/blocked by YouTube in 2025-26 (PO-token/SABR churn), so plan for residential proxies or, better, **rights-cleared sourcing**: podcast RSS enclosure MP3s (freely fetchable — that's what RSS is for), Creative Commons-filtered YouTube, partner/permission deals with FR+EN podcasters (many *want* clipping), and Twitch's official Clips/VOD endpoints. Copyright of the underlying content is a separate, bigger exposure than ToS: monetized clips of others' shows without permission is the industry's open secret and the main business risk, not a technical one.

### Transcription — Whisper family
- **faster-whisper (SYSTRAN)** = CTranslate2 Whisper, ~4x realtime+ on a consumer GPU; **whisperX** adds word-level alignment + pyannote diarization (needed for karaoke captions and speaker-aware clipping). **large-v3 / large-v3-turbo** are near-English quality on French (FR top-5 resource language for Whisper).
- API alternatives: **Groq Whisper large-v3-turbo $0.04/audio-hour** (large-v3 $0.111/hr); **OpenAI Whisper API $0.006/min ($0.36/hr)**; **Deepgram Nova-3 $0.0043/min batch (~$0.26/hr)**, $200 free credit, good FR support.

### Highlight detection (the hard part)
- Established pattern: transcribe → chunk transcript with timestamps → LLM scores segments for hook/emotion/self-containedness → merge to 20-60s windows. Cheap with Gemini Flash / GPT-4o-mini / Claude Haiku.
- **ClipsAI** (github.com/ClipsAI/clipsai): Python lib, transcript-based clip finding + resizing; older but clean reference architecture.
- **FunClip** (github.com/modelscope/FunClip, Alibaba): FunASR + CAM++ speaker ID + LLM-assisted clipping; ZH-centric but instructive (speaker-targeted clipping).
- 2025-26 generation: **OpenShorts** (github.com/mutonby/openshorts — MIT core, faster-whisper + Gemini Flash highlights + MediaPipe/YOLOv8 reframe + burned styled subtitles + ElevenLabs dubbing, FastAPI, REST + MCP server, Docker; cloud from $12/mo); **AI-Youtube-Shorts-Generator** (SamurAIGPT / Anil-matcha — Whisper + LLM highlights + auto vertical crop); **opensource-clipping** (NaufalRizqullah — Whisper + Gemini + MediaPipe + pyannote, karaoke subtitles, B-roll, AI voice-over, auto-upload — closest single repo to the full spec); **ai-clipping-comfyui** (ComfyUI nodes: virality ranking, dedupe, face-tracked crop); **VideoHighlighter** (Aseiel — local Ollama visual+audio highlight detection). See github.com/topics/ai-clip-generator.
- Beyond-transcript signals worth adding: audio energy/laughter detection, Twitch chat-velocity spikes, multimodal LLMs (Gemini ingests video directly) for visual moments.

### Auto-reframe / face tracking
**MediaPipe** face detection (fast, CPU) or **YOLOv8-face + tracking** → smooth crop-window path → ffmpeg crop filter; fallback blurred-background pillarbox. OpusClip's "active speaker detection" ≈ diarization + face matching; pyannote + lip-motion heuristics reproduce it.

### Caption rendering
- **ffmpeg + ASS subtitles**: fastest, fully styled karaoke captions via libass; whisperX word timestamps → ASS `\k` tags. Zero cost, CPU-only.
- **Remotion** (React → video): best-looking animated captions; **free license for individuals & companies ≤3 employees**; otherwise $0.01/render, $100/mo minimum. Free tier covers a solo operator.
- **moviepy**: glue only, slow.

---

## 3. Source-discovery automation

- **YouTube Data API v3**: free, 10,000 units/day. `search.list` = 100 units; `videos.list`/`channels.list`/`playlistItems.list` = 1 unit. **Channel monitoring via free quota-less RSS** `https://www.youtube.com/feeds/videos.xml?channel_id=UC...` (poll hundreds of FR+EN channels free), then 1-unit `videos.list` calls for stats (view velocity); batched, ~500k videos/day of stats within quota.
- **Podcasts**: **PodcastIndex.org API** — free, open, ~4M+ feeds, language filter fr/en, recent/trending endpoints — ideal new-episode detector. **iTunes Search API** — free, `country=FR` for French catalog. Paid: Listen Notes, Podchaser. RSS enclosure URLs directly downloadable — legally cleanest ingestion path.
- **Twitch Helix API**: free. `GET /clips` by broadcaster/game sorted by views with time windows → "top FR clips of last 24h" trivial (`broadcaster_language=fr`); `GET /videos` for VODs; 2025-26 added **Clip-from-VOD creation API** (5-60s, open beta). Chat-rate spikes via IRC/EventSub = free highlight signal.
- **Kick**: official dev API (Feb 2025, github.com/KickEngineering/KickDevDocs) but thin; most use scrapers (Apify).
- **TikTok trends**: no official public trends API. **TikTok Creative Center** (trending hashtags/songs/creators per country, FR + EN charts) scraped via Apify actors (clockworks/tiktok-trends-scraper etc., a few $/1k results).
- **Ranking**: score = source authority × recency × velocity (RSS/stats deltas) × topic-trend match (Creative Center, per-locale) × historical clip performance in own analytics. Two parallel locale queues (FR, EN); LLM pass over episode titles/descriptions filters before spending transcription compute.

---

## 4. AI voice / persona layer

**TTS (FR + EN both well-covered):**

| Provider | Price (2026) | FR/EN notes |
|---|---|---|
| **ElevenLabs** | Free 10k credits / Starter $6 / **Creator $22 (~120 min multilingual)** / Pro $99. API ≈ $50/M chars (Turbo/Flash v2.5), ~$100/M (v3) | Best expressiveness + cloning; excellent French; default for a persona voice. Cost driver at scale. |
| **Cartesia Sonic-3** | ~$35/M chars (~4x cheaper than ElevenLabs) | Near-ElevenLabs quality 2026, 40ms latency; French supported; strong cost/quality pick. |
| **OpenAI TTS / gpt-4o-mini-tts** | $15/M chars | Solid, cheap; decent FR; no cloning/persona control. |
| **Azure Neural TTS** | ~$16/M chars, many fr-FR/fr-CA voices | Enterprise-stable, free monthly tier. |
| **Kokoro-82M** (open) | Free (Apache); CPU-capable | Jan 2026 #1 TTS Arena; **French voicepack weaker than EN; no cloning**. |
| **XTTS-v2 (Coqui)** (open) | Free but CPML non-commercial license — caution | 17 languages, 6-second cross-lingual cloning (same persona voice FR *and* EN). Chatterbox (Resemble, MIT) = 2025-26 open cloning alternative. |

**Avatars:**
- **HeyGen**: subs Creator $29 / Pro $99 / Business $149+; **API pay-as-you-go (free API credits removed Feb 2026): ~$1/min standard, ~$4/min Avatar IV 1080p, Avatar V ~$3/min**. Best quality; expensive at 150 clips/mo.
- **D-ID**: cheapest basic talking heads, aging. **Hedra**: ~$2.9/min effective, expressive stylized personas.
- **Open source**: **LivePortrait** (best self-host pick, near-real-time on modern GPU), SadTalker (dated), Wav2Lip/MuseTalk/LatentSync (lip-sync only), EchoMimic, Hallo3 (2025, long-clip consistency). Runnable on rented RTX 4090.
- **Cheapest credible persona**: **PNG-tuber animated character** — 2-4 mouth/eye states switched by TTS amplitude, ffmpeg overlay. Zero marginal cost; matches accepted TikTok commentary aesthetic. Recommended v1.

---

## 5. Publishing / scheduling to TikTok

- **TikTok Content Posting API (direct)**: free, but **unaudited clients post SELF_ONLY (private)** — max 5 users/24h; API returns "success" with no warning video is invisible. Public posting requires **audit** (exact UX/consent compliance; days-to-weeks, rejections common). Needs verified dev account + HTTPS site. Plan 2-6 weeks.
- **Third-party posting APIs** (they hold the audited app):
  - **Upload-Post**: free 10 uploads/mo; paid from **$24/mo ($16 annual), unlimited** — cheapest.
  - **Blotato**: **$29/mo**, 20 accounts, REST API + MCP server.
  - **Postiz**: hosted $29–99; **self-hosted free (AGPL)** but self-host = bring your own TikTok app = do the audit yourself.
  - **Ayrshare**: Premium $149/mo+. Overkill for one brand.
  - **Metricool/Buffer**: no usable public posting APIs.
- **Recommended**: Upload-Post or Blotato to launch, pursue own TikTok audit in parallel.

---

## 6. End-to-end cost estimate — ~5 videos/day (150/mo), bilingual FR+EN

**Stack A — API-only, no GPU, PNG-tuber persona (lean launch): ≈ $70–125/mo**
Discovery free + Apify ~$5-10 · Groq transcription 120h ~$5 · highlight LLM ~$5-15 · scripts ~$2 · TTS $5-22 (Cartesia/ElevenLabs) · persona $0 · render ffmpeg on 8-vCPU VPS ~$20-40 · publishing $24-29.

**Stack B — self-host GPU + open avatar: ≈ $90–160/mo** (RunPod RTX 4090 serverless ~$1.10/hr active; 150 clips ≈ 8-12 GPU-hrs; voice-cloned XTTS/Chatterbox at $0 marginal).

**Stack C — premium avatar (HeyGen)**: Stack A + $150-450/mo → $250-550/mo. Only after format proves out.

**Stack D — buy-not-build**: Vizard API ($29-39) + Crayo ($39) + Upload-Post ($24) ≈ $90-100/mo, much less code, but no reaction layer and weaker FR persona control.

**Bottom line**: compute/API cost is trivial (~$100/mo class) at 5/day; real costs are (1) TikTok publishing/audit path, (2) rights to source content, (3) highlight-quality bar. The differentiated, undersupplied piece: automated FR/EN reaction-persona layer — no incumbent ships it.

---

## Sources
- OpusClip: https://www.opus.pro/pricing · https://www.opus.pro/blog/twitch-vod-to-clips-api · https://www.eesel.ai/blog/opusclip-pricing · https://checkthat.ai/brands/opusclip/pricing
- Klap: https://klap.app/pricing · https://www.iaproductif.fr/avis-klap-app/ · https://promptfacile.fr/outils/klap/
- Vizard: https://vizard.ai/pricing · https://vizard.ai/api · https://docs.vizard.ai/docs/pricing
- Comparisons 2026: https://www.ssemble.com/blog/best-ai-clipping-tools-2026 · https://www.choppity.com/blog/best-opus-clip-alternatives/ · https://montage.app/blog/state-of-ai-video-clipping-2026-benchmark-report · https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026
- Crayo/Spikes: https://tugan.ai/blog/crayo-ai-review · https://fluxnote.io/guides/crayoai-pricing-guide-2026 · https://makerstack.co/reviews/spikes-studio-review/ · https://creatoreconomytools.com/tool/spikes-studio
- Reaction tools: https://www.revid.ai/tools/ai-reaction-video-generator · https://www.medeo.app/video-generator/reaction · https://www.dreamfaceapp.com/tools/fake-stream-generator
- Open source: https://github.com/mutonby/openshorts · https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator · https://github.com/NaufalRizqullah/opensource-clipping · https://github.com/Anil-matcha/ai-clipping-comfyui · https://github.com/ClipsAI/clipsai · https://github.com/modelscope/FunClip · https://github.com/Aseiel/VideoHighlighter
- yt-dlp legality: https://audioutils.com/blog/is-yt-dlp-legal · https://www.navthemes.com/is-yt-dlp-legal/ · https://lynote.ai/blog/download-youtube-videos-legally
- Whisper/STT: https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks · https://convertaudiototext.com/blog/whisper-large-v3-explained · https://apio.sh/apis/groq-speech-to-text · https://tokenmix.ai/blog/whisper-api-pricing · https://convertaudiototext.com/blog/deepgram-nova-3-explained
- Remotion: https://www.remotion.dev/docs/license/pricing
- YouTube API: https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota · https://outlierkit.com/resources/youtube-api-quota/
- Podcast APIs: https://www.podchaser.com/articles/api/best-podcast-api · https://taddy.org/blog/best-podcast-api-tools
- Twitch/Kick: https://dev.twitch.tv/docs/api/clips/ · https://discuss.dev.twitch.com/t/introducing-clip-api-improvements-and-clip-from-vod-in-open-beta/64492 · https://github.com/KickEngineering/KickDevDocs
- TikTok trends scraping: https://apify.com/clockworks/tiktok-trends-scraper
- TTS: https://elevenlabs.io/pricing · https://futureagi.com/blog/best-text-to-speech-providers-2026/ · https://www.pkgpulse.com/guides/elevenlabs-vs-openai-tts-vs-cartesia-text-to-speech-2026 · https://localaimaster.com/blog/kokoro-vs-xtts-vs-chatterbox
- Avatars: https://www.arcade.software/post/heygen-pricing · https://www.hedra.com/pricing · https://lipsync.com/blog/open-source-lip-sync · https://www.pixazo.ai/blog/best-open-source-ai-lip-sync-models
- TikTok Posting API: https://developers.tiktok.com/doc/content-posting-api-get-started · https://developers.tiktok.com/doc/content-sharing-guidelines · https://bundle.social/blog/tiktok-api-approval
- Posting APIs: https://www.upload-post.com/pricing-comparison/ · https://www.blotato.com/blog/best-social-media-api-tools · https://docs.postiz.com/providers/tiktok
- GPU: https://www.thundercompute.com/blog/runpod-pricing-vs-thunder-compute
