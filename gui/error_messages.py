from __future__ import annotations


TRIAL_QUOTA_EXHAUSTED_MESSAGE = (
    "试用额度不足，当前 token 的免费额度已经用完。\n\n"
    "请在右上角齿轮图标 → 火山引擎试用中重新申请/更换 token，"
    "或改用自己的火山引擎 App Key。"
)


def friendly_runtime_error(message: str) -> str:
    lowered = (message or "").lower()
    if "quota_exhausted" in lowered:
        return TRIAL_QUOTA_EXHAUSTED_MESSAGE
    if "token_in_use" in lowered:
        return "这个 token 已经被人占用啦（阿里一 token 一人的限制，建议切换火山引擎）"
    return message
