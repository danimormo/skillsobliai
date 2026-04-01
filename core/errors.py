class SkillBaseError(Exception):
    def __init__(self, message: str, skill: str, code: str):
        self.message = message
        self.skill = skill
        self.code = code
        super().__init__(message)


class TokenExpiredError(SkillBaseError):
    pass


class TokenMissingError(SkillBaseError):
    pass


class RateLimitError(SkillBaseError):
    pass


class InvalidParamsError(SkillBaseError):
    pass


class UpstreamError(SkillBaseError):
    pass


class InsufficientCreditsError(SkillBaseError):
    pass


class IntegrationNotConnectedError(SkillBaseError):
    pass


class InvalidApiKeyError(SkillBaseError):
    pass
