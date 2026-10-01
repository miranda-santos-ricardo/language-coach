import pytest

from app.services.stt_language import to_stt_language

@pytest.mark.parametrize(
    ("locale","expected"),
    [
        ("fr-CA", "fr"),
        ("fr-FR", "fr"),
        ("en-CA", "en"),
        ("en-US", "en"),
        ("en-GB", "en"),
    ],
)

def test_to_stt_language_maps_supported_locales(
    locale:str,
    expected:str
) -> None:
    assert to_stt_language(locale) == expected

def test_to_stt_language_rejects_unknown_locale() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported STT locale"
    ):
        to_stt_language("xx-YY")