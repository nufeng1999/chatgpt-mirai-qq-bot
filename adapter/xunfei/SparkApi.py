import _thread as thread
import base64
import datetime
import hashlib
import hmac
import json
import random
import ssl
from datetime import datetime
from time import mktime
from typing import Dict, List
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import websocket

# 一次请求最大的token数
MAX_TOKENS = 2048


class SparkApi:
    def __init__(
        self, app_id: str, api_key: str, api_secret: str, spark_url: str, uid: str
    ) -> None:
        """初始化"""
        self.app_id: str = app_id
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.host: str = urlparse(spark_url).netloc
        self.path: str = urlparse(spark_url).path
        self.spark_url: str = spark_url
        self.answer: str = ""
        self.uid: str = uid

    def create_url(self) -> str:
        """生成url"""
        date = format_date_time(mktime(datetime.now().timetuple()))
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{base64.b64encode(signature_sha).decode(encoding="utf-8")}"'
        v = {
            "authorization": base64.b64encode(
                authorization_origin.encode("utf-8")
            ).decode(encoding="utf-8"),
            "date": date,
            "host": self.host,
        }
        return f"{self.spark_url}?{urlencode(v)}"

    def on_error(self, ws, error) -> None:
        """收到websocket错误的处理"""
        self.answer += error

    def on_close(self, ws, one, two) -> None:
        """收到websocket关闭的处理"""
        self.answer += "  "

    def on_open(self, ws) -> None:
        """收到websocket连接建立的处理"""
        thread.start_new_thread(self.run, (ws,))

    def run(self, ws, *args) -> None:
        data = json.dumps(self.gen_params(domain=ws.domain, question=ws.question))
        ws.send(data)

    def on_message(self, ws, message) -> None:
        """收到websocket消息的处理"""
        data = json.loads(message)
        code = data["header"]["code"]
        if code != 0:
            print(f"请求错误: {code}, {data}")
            ws.close()
        else:
            choices = data["payload"]["choices"]
            status = choices["status"]
            content = choices["text"][0]["content"]
            self.answer += content
            if status == 2:
                ws.close()

    def gen_params(self, domain: str, question: str) -> Dict[str, Dict]:
        """通过appid和用户的提问来生成请参数"""
        return {
            "header": {"app_id": self.app_id, "uid": self.uid},
            "parameter": {
                "chat": {
                    "domain": domain,
                    "random_threshold": 0.5,
                    "max_tokens": MAX_TOKENS,
                    "auditing": "default",
                }
            },
            "payload": {"message": {"text": question}},
        }


class V2BotClient:
    def __init__(self, appid: str, api_secret: str, api_key: str) -> None:
        """初始化"""
        self.answer: str = ""
        self.text: List[Dict] = []
        self.appid: str = appid
        self.api_secret: str = api_secret
        self.api_key: str = api_key
        self.domain: str = "generalv2"
        self.spark_url: str = "ws://spark-api.xf-yun.com/v2.1/chat"
        self.uid = str(random.randint(1000000000, 9999999999))

    def ask(self, question: str) -> str:
        """向机器人提问"""
        self.set_question(question)
        ws_param = SparkApi(
            self.appid, self.api_key, self.api_secret, self.spark_url, self.uid
        )
        websocket.enableTrace(False)
        ws_url = ws_param.create_url()
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=ws_param.on_message,
            on_error=ws_param.on_error,
            on_close=ws_param.on_close,
            on_open=ws_param.on_open,
        )
        ws.appid = self.appid
        ws.question = self.text
        ws.domain = self.domain
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        self.answer = ws_param.answer
        self.text.append({"role": "assistant", "content": self.answer})
        return self.answer

    def get_length(self) -> int:
        """获取已经输入的字符数"""
        return sum(len(content["content"]) for content in self.text)

    def set_question(self, question: str) -> None:
        """设置问题"""
        self.text.append({"role": "user", "content": question})
        while self.get_length() > 8000:
            del self.text[0]


class V1BotClient(V2BotClient):
    """V1版本的接口"""

    def __init__(self, appid: str, api_secret: str, api_key: str) -> None:
        super().__init__(appid, api_secret, api_key)
        self.domain = "general"
        self.spark_url = "ws://spark-api.xf-yun.com/v1.1/chat"