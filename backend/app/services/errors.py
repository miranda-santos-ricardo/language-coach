class ServiceError(Exception):
    """Base class for expected application-service errors."""


class UserNotFoundError(ServiceError):
    pass


class LanguageNotFoundError(ServiceError):
    pass


class LanguageVariantNotFoundError(ServiceError):
    pass


class LanguageVariantMismatchError(ServiceError):
    pass


class CommunicationRegisterNotFoundError(ServiceError):
    pass


class InactiveReferenceDataError(ServiceError):
    pass


class RegisterModeNotAllowedError(ServiceError):
    pass


class DuplicateLanguageProfileError(ServiceError):
    pass


class LanguageProfileNotFoundError(ServiceError):
    pass
