from __future__ import annotations


PROVIDER_CAPABILITIES = {
    "veo": {
        "models": ["veo-3.1-generate-001", "veo-3.1-fast-generate-001"],
        "aspect_ratios": ["16:9", "9:16"],
        "durations_sec": [4, 6, 8],
        "supports_audio": True,
        "supports_image_to_video": True,
        "supports_callback": False,  # fallback poll-first unless you build wrapper callback infra
    },
    "runway": {
        "models": ["gen4_turbo", "gen4_aleph"],
        "aspect_ratios": ["16:9", "9:16"],
        "durations_sec": [5, 10],
        "supports_audio": False,
        "supports_image_to_video": True,
        "supports_callback": True,
    },
    "kling": {
        "models": ["kling-2.1", "kling-3.0"],
        "aspect_ratios": ["16:9", "9:16"],
        "durations_sec": [5, 10],
        "supports_audio": False,
        "supports_image_to_video": True,
        "supports_callback": True,
    },
}