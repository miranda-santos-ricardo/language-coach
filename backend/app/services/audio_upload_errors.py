class AudioUploadError(Exception):
    """Base exception for invalid audio uploads."""


class EmptyAudioFileError(AudioUploadError):
    """Uploaded audio file is empty."""


class UnsupportedAudioTypeError(AudioUploadError):
    """Uploaded audio type is not supported."""


class AudioFileTooLargeError(AudioUploadError):
    """Uploaded audio exceeds the configured size limit."""