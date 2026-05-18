import httpx
import logging
import re
from app_config import get_config_value


def redact_telegram_token(text: str, token: str) -> str:
    redacted = text.replace(token, "<tg-token>") if token else text
    return re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", "<tg-token>", redacted)

class TelegramBot:
    def __init__(self) -> None:
        pass

    async def send_message(self, text: str) -> bool:
        """ 异步发送 TG 消息 """
        token = get_config_value("TG_BOT_TOKEN")
        chat_id = get_config_value("TG_CHAT_ID")
        parse_mode = get_config_value("TG_PARSE_MODE", "MarkdownV2")
        disable_web_page_preview = get_config_value("TG_DISABLE_WEB_PREVIEW", "true").lower() in {"1", "true", "yes", "on"}
        api_url = f"https://api.telegram.org/bot{token}/sendMessage" if token else ""

        if not token or not chat_id:
            logging.error("TG 配置缺失，无法推送")
            return False
            
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        try:
            # 使用 httpx 进行异步请求
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(api_url, json=payload)
                if resp.status_code == 200:
                    return True
                else:
                    detail = redact_telegram_token(resp.text[:500], token)
                    logging.error(f"TG 推送失败: {resp.status_code} {detail}")
                    return False
        except Exception as e:
            logging.error(f"TG 连接异常: {redact_telegram_token(repr(e), token)}")
            return False
