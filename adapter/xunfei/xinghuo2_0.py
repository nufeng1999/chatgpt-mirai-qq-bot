from io import BytesIO

from typing import Generator

from adapter.botservice import BotAdapter
from config import Xinghuo2_0_CookiePath
from constants import botManager
from exceptions import BotOperationNotSupportedException
from loguru import logger
import httpx
import base64
from PIL import Image
import random
# import SparkApi
from .SparkApi import V2BotClient

appid = ""     #填写控制台中获取的 APPID 信息
api_secret = ""   #填写控制台中获取的 APISecret 信息
api_key =""    #填写控制台中获取的 APIKey 信息

#用于配置大模型版本，默认“general/generalv2”
domain = "generalv3"   # v1.5版本
# domain = "generalv2"    # v2.0版本
#云端环境的服务地址
Spark_url = "ws://spark-api.xf-yun.com/v3.1/chat"  # v1.5环境的地址
# Spark_url = "ws://spark-api.xf-yun.com/v2.1/chat"  # v2.0环境的地址

class Xinghuo2_0_Adapter(BotAdapter):
    """
    Credit: https://github.com/dfvips/xunfeixinghuo
    """
    account: Xinghuo2_0_CookiePath

    def __init__(self, session_id: str = ""):
        super().__init__(session_id)

        self.session_id = session_id
        self.account = botManager.pick('xinghuo2-0-cookie')
        self.proxy =self.account.proxy
        self.APPID =self.account.APPID
        self.APISecret =self.account.APISecret
        self.APIKey =self.account.APIKey
        self.bot2 = V2BotClient(
                appid=self.APPID,
                api_key=self.APIKey,
                api_secret=self.APISecret,
            )
    async def delete_conversation(self, session_id):
        pass
    async def rollback(self):
        raise BotOperationNotSupportedException()

    async def on_reset(self):
        raise BotOperationNotSupportedException()

    async def new_conversation(self):
        raise BotOperationNotSupportedException()
    
    async def ask(self, prompt) -> Generator[str, None, None]:
        full_response = self.bot2.ask(prompt)
        yield full_response
        
        logger.debug(f"[Xinghuo2_0] - {full_response}")

    async def preset_ask(self, role: str, text: str):
        if role.endswith('bot') or role in {'assistant', 'xinghuo'}:
            logger.debug(f"[预设] 响应：{text}")
            yield text
        else:
            logger.debug(f"[预设] 发送：{text}")
            item = None
            async for item in self.ask(text): ...
            if item:
                logger.debug(f"[预设] Chatbot 回应：{item}")

