class SkillBaseError(Exception):
    def __init__(self, message: str, skill: str = "", code: str = ""):
        super().__init__(message)
        self.message = message
        self.skill = skill
        self.code = code

    def to_dict(self) -> dict:
        return {"error": self.message, "code": self.code, "skill": self.skill}


class TokenExpiredError(SkillBaseError):
    pass


class TokenMissingError(SkillBaseError):
    pass


class IntegrationNotConnectedError(SkillBaseError):
    pass


class RateLimitError(SkillBaseError):
    pass


class UpstreamError(SkillBaseError):
    pass


class InvalidParamsError(SkillBaseError):
    pass


class InvalidApiKeyError(SkillBaseError):
    pass


class InsufficientCreditsError(SkillBaseError):
    pass


class VertexAIError(SkillBaseError):
    pass


class VertexAITimeoutError(SkillBaseError):
    pass


class GoogleVisionError(SkillBaseError):
    pass


class ManusError(SkillBaseError):
    pass


class ManusTimeoutError(SkillBaseError):
    pass


class ShopifyError(SkillBaseError):
    pass


class MetaAPIError(SkillBaseError):
    pass
