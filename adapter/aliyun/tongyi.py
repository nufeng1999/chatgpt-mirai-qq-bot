from io import BytesIO
import uuid
import json
from typing import Generator
import re
from adapter.botservice import BotAdapter
from adapter.educational_reminder import Educational_Reminder
from config import TongyiCookiePath
from constants import botManager
from exceptions import BotOperationNotSupportedException
from loguru import logger
import httpx
import base64
from PIL import Image
import random

er=Educational_Reminder()
class TongyiAdapter(BotAdapter):
    """
    Credit: 
    """
    account: TongyiCookiePath
    client: httpx.AsyncClient

    def __init__(self, session_id: str = ""):
        super().__init__(session_id)
        self.session_id = session_id
        logger.debug(f"[Tongyi] self.session_id - {self.session_id}")
        self.account = botManager.pick('tongyi-cookie')
        self.client = httpx.AsyncClient(proxies=self.account.proxy)
        self.sessionId = ''
        self.TOKEN = self.account.TOKEN
        self.__setup_headers(self.client)
        self.parentMsgId = '0'
    def _getNewmsgId(self):
        uuid_obj = uuid.uuid4()
        uuid_str = uuid_obj.hex
        return uuid_str
    
    async def rollback(self):
        raise BotOperationNotSupportedException()

    async def on_reset(self):
        try:
            
            if (
                    self.account.auto_remove_old_conversations
                    and self.sessionId !=''
            ):
                await self.delete_Session()
        except Exception:
            logger.warning("删除会话记录失败。")
        await self.client.aclose()
        self.client = httpx.AsyncClient(proxies=self.account.proxy)
        self.sessionId = ''
        self.__setup_headers(self.client)
        self.parentMsgId = '0'

    def __setup_headers(self, client):
        if len(self.sessionId)>1:
            client.headers['Cookie'] = f"cna=3vgAHN0JakkCAduYJoAqhhA8; munb=2206556595003; t=68766d361814112f406837117df5c72a; login_current_pk=1619803085428437; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_tongyi_ticket=rokUaHrrXUaI5WM5mLOWAYQsjDCvmmOGeMHriySSS7B_HrKbxwz7hGsS9*IIQJ2e0; cnaui=1619803085428437; aui=1619803085428437; yunpk=1619803085428437; XSRF-TOKEN={self.TOKEN}; sca=a8dc32fe; _samesite_flag_=true; cookie2=1d178ffa569545a65f12f384fd43b25e; _tb_token_=7f1e6ef698764; atpsida=96c6536b68748f8c374c279b_1699493790_4; login_aliyunid_csrf=_csrf_tk_1205199492843228; l=fBaDwW0uP_ZzG3OhKOfwFurza77OQIRfguPzaNbMi9fP9Xf65foRW1FLS4TBCnGVEstyv3-P4wzWBXLsWy4FhdBGOeHWX3srndLnwpzHU; isg=BFdXf5yj_uLCGHwHJbi7LtCT5suhnCv-njAyEKmEbSaN2HYaoG7IT0s-PnhGMAN2; tfstk=c9S5BF93ibc5rEH41HwVGEE9mxtcakhMn8OcF5WI2nngIABWMsD-bCOG99cvYppf."
        else:
            client.headers['Cookie'] = f"cna=3vgAHN0JakkCAduYJoAqhhA8; munb=2206556595003; t=68766d361814112f406837117df5c72a; login_current_pk=1619803085428437; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_tongyi_ticket=rokUaHrrXUaI5WM5mLOWAYQsjDCvmmOGeMHriySSS7B_HrKbxwz7hGsS9*IIQJ2e0; cnaui=1619803085428437; aui=1619803085428437; yunpk=1619803085428437; XSRF-TOKEN={self.TOKEN}; sca=a8dc32fe; _samesite_flag_=true; cookie2=1d178ffa569545a65f12f384fd43b25e; _tb_token_=7f1e6ef698764; atpsida=96c6536b68748f8c374c279b_1699493790_4; login_aliyunid_csrf=_csrf_tk_1205199492843228; l=fBaDwW0uP_ZzG3OhKOfwFurza77OQIRfguPzaNbMi9fP9Xf65foRW1FLS4TBCnGVEstyv3-P4wzWBXLsWy4FhdBGOeHWX3srndLnwpzHU; isg=BFdXf5yj_uLCGHwHJbi7LtCT5suhnCv-njAyEKmEbSaN2HYaoG7IT0s-PnhGMAN2; tfstk=c9S5BF93ibc5rEH41HwVGEE9mxtcakhMn8OcF5WI2nngIABWMsD-bCOG99cvYppf."

        client.headers['Host'] = f"qianwen.aliyun.com"
        client.headers['Connection'] = f"keep-alive"
        client.headers['sec-ch-ua'] = '"Microsoft Edge";v="117", "Not;A=Brand";v="8", "Chromium";v="117"'
        client.headers['X-XSRF-TOKEN'] = f"{self.TOKEN}"
        client.headers['sec-ch-ua-mobile'] = f"?0"
        client.headers['X-Platform'] = f"pc_tongyi"
        client.headers['User-Agent'] = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.36"
        client.headers['Content-Type'] = f"application/json"
        client.headers['accept'] = f"text/event-stream"
        # client.headers['accept'] = f"application/json, text/plain, */*"
        client.headers['bx-v'] = f"2.5.3"
        client.headers['sec-ch-ua-platform'] = '"Windows"'
        client.headers['Origin'] = f"https://qianwen.aliyun.com"
        client.headers['Sec-Fetch-Site'] = f"same-origin"
        client.headers['Sec-Fetch-Mode'] = f"cors"
        client.headers['Sec-Fetch-Dest'] = f"empty"
        client.headers['Referer'] = f"https://qianwen.aliyun.com/"
        # client.headers['Accept-Encoding'] = f" gzip, deflate, br"
        # client.headers['Accept-Language'] = f"zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
        # client.headers['Cookie'] = f"cna=3vgAHN0JakkCAduYJoAqhhA8; munb=2206556595003; t=68766d361814112f406837117df5c72a; login_current_pk=1619803085428437; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_tongyi_ticket=rokUaHrrXUaI5WM5mLOWAYQsjDCvmmOGeMHriySSS7B_HrKbxwz7hGsS9*IIQJ2e0; cnaui=1619803085428437; aui=1619803085428437; yunpk=1619803085428437; XSRF-TOKEN={self.TOKEN}; sca=a8dc32fe; _samesite_flag_=true; cookie2=1d178ffa569545a65f12f384fd43b25e; _tb_token_=7f1e6ef698764; atpsida=96c6536b68748f8c374c279b_1699493790_4; login_aliyunid_csrf=_csrf_tk_1205199492843228; l=fBaDwW0uP_ZzG3OhKOfwFurza77OQIRfguPzaNbMi9fP9Xf65foRW1FLS4TBCnGVEstyv3-P4wzWBXLsWy4FhdBGOeHWX3srndLnwpzHU; isg=BFdXf5yj_uLCGHwHJbi7LtCT5suhnCv-njAyEKmEbSaN2HYaoG7IT0s-PnhGMAN2; tfstk=c9S5BF93ibc5rEH41HwVGEE9mxtcakhMn8OcF5WI2nngIABWMsD-bCOG99cvYppf."
    def __setup_headers2(self, client):

        client.headers['Host'] = f"qianwen.aliyun.com"
        client.headers['Connection'] = f"keep-alive"
        client.headers['sec-ch-ua'] = 'Microsoft Edge";v="117", "Not;A=Brand";v="8", "Chromium";v="117"'
        client.headers['X-XSRF-TOKEN'] = f"{self.TOKEN}"
        client.headers['sec-ch-ua-mobile'] = f"?0"
        client.headers['X-Platform'] = f"pc_tongyi"
        client.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.36'
        client.headers['Content-Type'] = f"application/json"
        client.headers['Accept'] = f"application/json, text/plain, */*"
        client.headers['bx-v'] = f"2.5.3"
        client.headers['sec-ch-ua-platform'] = '"Windows"'
        client.headers['Origin'] = f"https://qianwen.aliyun.com"
        client.headers['Sec-Fetch-Site'] = f"same-origin"
        client.headers['Sec-Fetch-Mode'] = f"cors"
        client.headers['Sec-Fetch-Dest'] = f"empty"
        client.headers['Referer'] = f"https://qianwen.aliyun.com/"
        client.headers['Accept-Encoding'] = f"gzip, deflate, br"
        client.headers['Accept-Language'] = f"zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
        client.headers['Cookie'] = f"cna=3vgAHN0JakkCAduYJoAqhhA8; munb=2206556595003; t=68766d361814112f406837117df5c72a; login_current_pk=1619803085428437; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_tongyi_ticket=rokUaHrrXUaI5WM5mLOWAYQsjDCvmmOGeMHriySSS7B_HrKbxwz7hGsS9*IIQJ2e0; cnaui=1619803085428437; aui=1619803085428437; yunpk=1619803085428437; XSRF-TOKEN={self.TOKEN}; sca=a8dc32fe; _samesite_flag_=true; cookie2=1d178ffa569545a65f12f384fd43b25e; _tb_token_=7f1e6ef698764; atpsida=cd2cabdeed1533444ddf3f0f_1699499288_1; login_aliyunid_csrf=_csrf_tk_1205199492843228; l=fBaDwW0uP_ZzGkCWBOfZPurza779lIRVguPzaNbMi9fP9p5y57gFW1FKGfT2CnGVEsLB73-P4wzWBz8tNy4Fh6FaOUDWX3szgd8nwpzHU; isg=BA0NU0lIVKB2SvblA05hLC5tHCmH6kG8UF448k-SLaQTRi_4EDjYjTgQtNoghll0; tfstk=cZCABpvaauq04HwlFGeubpOkjPkAaQUwjxtn6s0yRE5nC4cnTsqAt6Q8crTBYnUR."
    def __setup_headers3(self, client):
        
        client.headers['Host'] = f"qianwen.aliyun.com"
        client.headers['Connection'] = f"keep-alive"
        client.headers['sec-ch-ua'] = 'Microsoft Edge";v="117", "Not;A=Brand";v="8", "Chromium";v="117"'
        client.headers['X-XSRF-TOKEN'] = f"{self.TOKEN}"
        client.headers['sec-ch-ua-mobile'] = f"?0"
        client.headers['X-Platform'] = f"pc_tongyi"
        client.headers['User-Agent'] = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.36"
        client.headers['Content-Type'] = f"application/json"
        client.headers['Accept'] = f"application/json, text/plain, */*"
        client.headers['bx-v'] = f"2.5.3"
        client.headers['sec-ch-ua-platform'] = '"Windows"'
        client.headers['Origin'] = f"https://qianwen.aliyun.com"
        client.headers['Sec-Fetch-Site'] = f"same-origin"
        client.headers['Sec-Fetch-Mode'] = f"cors"
        client.headers['Sec-Fetch-Dest'] = f"empty"
        client.headers['Referer'] = f"https://qianwen.aliyun.com/?chatId=f8b6d94acded427184fc814a542705a7"
        client.headers['Accept-Encoding'] = f"gzip, deflate, br"
        client.headers['Accept-Language'] = f"zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
        client.headers['Cookie'] = f"cna=3vgAHN0JakkCAduYJoAqhhA8; munb=2206556595003; t=68766d361814112f406837117df5c72a; login_current_pk=1619803085428437; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_tongyi_ticket=rokUaHrrXUaI5WM5mLOWAYQsjDCvmmOGeMHriySSS7B_HrKbxwz7hGsS9*IIQJ2e0; cnaui=1619803085428437; aui=1619803085428437; yunpk=1619803085428437; XSRF-TOKEN={self.TOKEN}; sca=a8dc32fe; _samesite_flag_=true; cookie2=1d178ffa569545a65f12f384fd43b25e; _tb_token_=7f1e6ef698764; atpsida=a666a4db73f7185a691521ee_1699508805_4; login_aliyunid_csrf=_csrf_tk_1205199492843228; l=fBaDwW0uP_ZzG1lUBO5alurza77TfIRf1sPzaNbMiIEGa61fTF_fkNCT92JM7dtjgTfvDety4g7UPdFD88z38x1Z0gGiFhK54spw-bpU-L5..; isg=BFxc6Kk8VSNAPycWWkHAz3fqLXoO1QD_GTmJoTZdgscpgf8LXuRsjuJ35el5CThX; tfstk=cY5RBR9UgoqoJ-wchMe0YdwAh3Ada7zexYti9_04b1CrjucKOs2Rs1QYVzT6b3UA."

    async def delete_Session(self):
        self.__setup_headers3(self.client)
        return await self.client.post("https://qianwen.aliyun.com/deleteSession", json={
            'sessionId': self.sessionId
        })

    async def new_session(self,prompt):
        self.__setup_headers2(self.client)
        req = await self.client.post(
            url="https://qianwen.aliyun.com/addSession",
            json={"firstQuery":prompt,"sessionType":"text_chat"}
        )
        req.raise_for_status()
        logger.debug(f"{req.text}")
        self.__check_response(req.json())
        # req.json()['success']
        self.sessionId = req.json()['data']['sessionId']
        # self.conversation_id = req.json()['data']['userId']
        # self.parent_chat_id = 0
        # jsessionid_value = req.cookies.get("JSESSIONID")
        if self.sessionId:
            logger.debug(f"sessionId={self.sessionId}")
            # self.JSESSIONID=jsessionid_value
            #加入初始化预设内容，进行教育指导
            async for text in er.get_prompt():
                async for item in self.ask(text): ...
                if item:
                    logger.debug(f"[机器人会话初始化] Chatbot 回应：{item}")
            #
    async def ask(self, prompt) -> Generator[str, None, None]:
        if not self.sessionId:
            logger.debug(f"创建新的 sessionId")
            await self.new_session(prompt)

        full_response = ''
        self.__setup_headers(self.client)
        msgId=self._getNewmsgId()
        self.client.timeout = 120 # 设置为20秒
        async with self.client.stream(
                    "POST",
                    url="https://qianwen.aliyun.com/conversation",
                    json={
                        "action":"next",
                        "msgId":msgId,
                        "parentMsgId":self.parentMsgId,
                        "contents":[
                            {
                                "contentType":"text",
                                "content":prompt
                            }
                        ],
                        "timeout":120,
                        "openSearch":"false",
                        "sessionType":"text_chat",
                        "sessionId":self.sessionId,
                        "model":"",
                        "modelType":""
                        },
            ) as req:
            async for line in req.aiter_lines():
                if not line:
                    continue
                if line == 'data: [DONE]':
                    break
                if line == 'data:[geeError]':
                    yield "出现错误了，请重新发送一次消息再试。"
                    break
                json_string = line[len("data:"):]
                json_obj = json.loads(json_string)
                stopReason=json_obj['stopReason']
                if stopReason=='stop':
                    content=json_obj['content'][0]
                    msgId=json_obj['msgId']
                    full_response+=content
                    yield full_response
        self.parentMsgId=msgId
        logger.debug(f"[Tongyi] - {full_response}")


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

    def __check_response(self, resp):
        if not resp['errorCode'] is None:
            if int(resp['errorCode']) != 0:
                raise Exception(resp['errorMsg'])