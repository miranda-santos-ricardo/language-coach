STT_LANGUAGE_MAP: dict[str, str] = {
    "fr-CA": "fr",
    "fr-FR": "fr",
    "en-CA": "en",
    "en-US": "en",
    "en-GB": "en",
}


def to_stt_language(locale: str) -> str:
    try:
        return STT_LANGUAGE_MAP[locale]
    except KeyError as exc:
        raise ValueError(f"Unsupported STT locale: {locale}") from exc