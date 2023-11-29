from datetime import datetime
from io import BytesIO
import json

import re
from typing import Generator
from adapter.botservice import BotAdapter
from adapter.educational_reminder import Educational_Reminder
from config import XinghuoCookiePath
from constants import botManager
from exceptions import BotOperationNotSupportedException
from loguru import logger
import httpx
import base64
from PIL import Image
import random
from graia.ariadne.message.element import Image as GraiaImage
from platforms.onebot_assets.dbmng import DB_Manager

er=Educational_Reminder()
class XinghuoAdapter(BotAdapter):
    """
    Credit: https://github.com/dfvips/xunfeixinghuo
    """
    account: XinghuoCookiePath
    client: httpx.AsyncClient

    def __init__(self, session_id: str = ""):
        super().__init__(session_id)
        self.db_manager=DB_Manager()
        self.session_id = session_id
        self.account = botManager.pick('xinghuo-cookie')
        self.client = httpx.AsyncClient(proxies=self.account.proxy)
        self.JSESSIONID = ''
        self.group_id=self._get_groupid()
        self.__setup_headers(self.client)
        self.conversation_id = None
        # await self.new_conversation()
        self.parent_chat_id = ''
    async def delete_conversation(self, session_id):
        # https://xinghuo.xfyun.cn/iflygpt/u/chat-list/v1/del-chat-list
        # chatListId=77285826
        return await self.client.post("https://xinghuo.xfyun.cn/iflygpt/u/chat-list/v1/del-chat-list", json={
            'chatListId': session_id
        })
    def _getfd(self):
        six_digit_number = random.randint(100000, 999999)
        return str(six_digit_number)
    async def rollback(self):
        raise BotOperationNotSupportedException()

    async def on_reset(self):
        try:
            if (
                    self.account.auto_remove_old_conversations
                    and self.conversation_id is not None
            ):
                await self.delete_conversation(self.conversation_id)
        except Exception as e:
            logger.exception(e)
            logger.warning("删除会话记录失败。")
        await self.client.aclose()
        self.client = httpx.AsyncClient(proxies=self.account.proxy)
        self.__setup_headers(self.client)
        self.conversation_id = None
        self.parent_chat_id = ""

    def __setup_headers(self, client):
        if len(self.JSESSIONID)>1:
            client.headers['Cookie'] = f"JSESSIONID={self.JSESSIONID}; Hm_lvt_fe740601c79b0c00b6d5458d146aa5ef=1692802077; gr_user_id=2cce876c-4b84-4e7f-8a18-eb702aa5721b; _gcl_au=1.1.1650723755.1692802078; di_c_mti=3280d491-fd7c-6ac8-a18d-61db2223e631; d_d_app_ver=1.4.0; d_d_ci=8884210a-973b-66ef-b8af-7997d06d58fa; _ga=GA1.2.1734254928.1692802079; _ga_0KHV9JM0VW=GS1.1.1692802079.1.1.1692802309.59.0.0; account_id=17174791236; ssoSessionId={self.account.ssoSessionId}; gt_local_id=MUi5pLbtahiSWSfr8nlkt2yaSB3U6iwf2vf++s1pp9Ld2a1UuNMIwA=="
        else:
            client.headers['Cookie'] = f"ssoSessionId={self.account.ssoSessionId};appid=150b4dfebe;account_id=17174791236;gr_user_id=2cce876c-4b84-4e7f-8a18-eb702aa5721b;di_c_mti=3280d491-fd7c-6ac8-a18d-61db2223e631;gt_local_id=MUi5pLbtahiSWSfr8nlkt2yaSB3U6iwf2vf++s1pp9Ld2a1UuNMIwA==;Hm_lvt_fe740601c79b0c00b6d5458d146aa5ef=1692802077;"

        client.headers[
            'User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.36'
        # client.headers['Sec-Fetch-User'] = '?1'
        client.headers['Sec-Fetch-Mode'] = 'cors'
        client.headers['Sec-Fetch-Site'] = 'same-origin'
        client.headers['Sec-Fetch-Dest'] = 'empty'
        client.headers['Sec-Ch-Ua-Platform'] = '"Windows"'
        client.headers['Sec-Ch-Ua-Mobile'] = '?0'
        client.headers['Sec-Ch-Ua'] = '"Microsoft Edge";v="117", "Not;A=Brand";v="8", "Chromium";v="117"'
        client.headers['Origin'] = 'https://xinghuo.xfyun.cn'

        client.headers['Referer'] = 'https://xinghuo.xfyun.cn/desk'
        client.headers['Connection'] = 'keep-alive'
        client.headers['X-Requested-With'] = 'XMLHttpRequest'
        client.headers['Botweb'] = '0'
        # client.headers['Accept-Encoding'] = 'gzip, deflate, br',
        # client.headers['Content-Type'] = 'multipart/form-data; boundary=----WebKitFormBoundaryRC0XBgB35F9DADBO'
        # client.headers['accept'] = 'text/event-stream'
    async def new_conversation(self):
        req = await self.client.post(
            url="https://xinghuo.xfyun.cn/iflygpt/u/chat-list/v1/create-chat-list",
            json={'clientType': '1'}
        )
        req.raise_for_status()
        self.__check_response(req.json())
        self.conversation_id = req.json()['data']['id']
        self.parent_chat_id = ""
        jsessionid_value = req.cookies.get("JSESSIONID")
        if jsessionid_value:
            logger.debug(f"JSESSIONID={jsessionid_value}")
            self.JSESSIONID=jsessionid_value
            curtime = datetime.now()
            self.db_manager.insert_chatconversation(
                self.group_id,
                self.conversation_id,
                curtime.strftime("%Y-%m-%d %H:%M:%S")
            )
            #加入初始化预设内容，进行教育指导
            # async for text in er.get_prompt():
            #     async for item in self.ask(text): ...
            #     if item:
            #         logger.debug(f"[机器人会话初始化] Chatbot 回应：{item}")
            #

    async def ask(self, prompt) -> Generator[str, None, None]:
        await self.check_chatid()
        # if not self.conversation_id:
            # logger.debug(f"创建新的 conversation_id")
            # await self.new_conversation()
        sid=''
        full_response = ''
        encoded_data = ''
        self.__setup_headers(self.client)
        self.account.fd=self._getfd()
        self.client.timeout = 120 # 设置为20秒
        async with self.client.stream(
                    "POST",
                    url="https://xinghuo.xfyun.cn/iflygpt-chat/u/chat_message/chat",
                    # headers=chat_header,
                    data={
                        'fd': self.account.fd,
                        'isBot':'0',
                        'clientType': '1',
                        'text': prompt,
                        'chatId': self.conversation_id,
                        # 'sid': self.account.sid,
                        'GtToken': self.account.GtToken,
                        'clientType': '1',
                        'sid':self.parent_chat_id
                    },
            ) as req:
            contentendflag=0
            async for line in req.aiter_lines():
                if not line:
                    continue
                if line == 'data:<end>':
                    contentendflag=1
                    continue

                if line == '<sid>':
                    break

                if line == 'data:[geeError]':
                    logger.debug(f"[Xinghuo] {line}")
                    # yield "出现错误了，请重新发送一次消息再试。"
                    break
                encoded_data = line[len("data:"):]
                if(contentendflag==1):
                    sid=encoded_data
                    end = sid.index("<sid>")
                    sid = sid[:end]
                    self.parent_chat_id =sid
                    break
                if encoded_data == '[error]':
                    logger.debug(f"[Xinghuo] {encoded_data}")
                    # yield "出现错误了，请重新发送一次消息再试。"
                    break
                pattern = r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)$'
                if not re.match(pattern, encoded_data):
                    logger.debug(f"[Xinghuo] base64编码错误:{line}")
                    logger.debug(f"[Xinghuo] base64编码错误:{encoded_data}")
                    # yield "出现错误了，请重新发送一次消息再试。"
                    break
                missing_padding = len(encoded_data) % 4
                if missing_padding != 0:
                    encoded_data += '=' * (4 - missing_padding)
                decoded_data = base64.b64decode(encoded_data).decode('utf-8')
                if encoded_data != 'zw':
                    decoded_data = decoded_data.replace('\n\n', '\n')
                full_response += decoded_data
                ##处理图片
                # 使用正则表达式匹配大括号中的内容
                match = re.search(r'{.*}', full_response)

                if match:
                    try:
                        json_str = match.group(0)
                        logger.debug(f"[Xinghuo] multi_image_url {json_str}")
                        data = json.loads(json_str)
                        url_value = data.get('url')
                        if url_value:
                            yield GraiaImage(data_bytes=await self.__download_image(url_value))
                    except Exception as e:
                        logger.exception(e)
                else:
                    # logger.debug(f"[Xinghuo] {self.JSESSIONID}-{self.conversation_id}-{full_response}")
                    yield full_response
        jsessionid_value = req.cookies.get("JSESSIONID")
        if jsessionid_value:
            logger.debug(f"JSESSIONID={jsessionid_value}")
            self.JSESSIONID=jsessionid_value
        logger.debug(f"[Xinghuo] {self.JSESSIONID}-{self.conversation_id}- - {full_response}")

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

    def _get_groupid(self):
        input_string = self.session_id
        match = re.search(r'\d+', input_string)
        result=''
        if match:
            result = match.group()
        return result
    async def check_chatid(self) -> bool:
        code=-1
        if not self.conversation_id:
            self.conversation_id=self.db_manager.get_last_chatconversationid(self.group_id)
        if self.conversation_id:
            # 设置请求头、文件描述符和超时时间
            # self.__setup_headers(self.client)
            # self.account.fd = self._getfd()
            # self.client.headers=[]
            self.client.timeout = 120  # 设置为20秒
            # 发送请求检查 chatid
            r = await self.client.get(
                url=f"https://xinghuo.xfyun.cn/iflygpt/u/chat_history/all/{self.conversation_id}"
            )
            r_json = r.json()
            # logger.debug(f"check_chatid -{str(r_json)}")
            code = r_json.get('code')
            logger.debug(f"check_chatid -{self.conversation_id}--{code}")
        if code==0:
            return True
        await self.new_conversation()
        return True

    def __check_response(self, resp):
        if int(resp['code']) != 0:
            raise Exception(resp['msg'])
    async def __download_image(self, url: str) -> bytes:
        image = await self.client.get(url)
        image.raise_for_status()
        from_format = BytesIO(image.content)
        to_format = BytesIO()
        Image.open(from_format).save(to_format, format='JPEG')
        return to_format.getvalue()
