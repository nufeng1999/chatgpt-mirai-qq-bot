import asyncio
import itertools
import aiofiles
import re
from functools import partial
import sqlite3
from typing import Callable, Generator, List
from loguru import logger
import sys
import os
import threading
from config import Config
from aiocqhttp import CQHttp, Event, MessageSegment
from graia.ariadne.message.chain import MessageChain
from conversation import ConversationHandler
from datetime import datetime

config = Config.load_config()
current_file_path = os.path.abspath(sys.argv[0])


class ChatCache:
    """ """

    def response(self, event, is_group: bool):
        async def respond(resp):
            logger.debug(f"[OneBot] 尝试发送消息：{str(resp)}")
            try:
                # if not isinstance(resp, MessageChain):
                #     resp = MessageChain(resp)
                # resp = self.transform_from_message_chain(resp)
                # # skip voice
                # if config.response.quote and "[CQ:record,file=" not in str(resp):
                #     resp = MessageSegment.reply(event.message_id) + resp
                return await self.bot.send(event, resp)
            except Exception as e:
                logger.exception(e)
                # raise e

                # logger.warning("原始消息发送失败，尝试通过转发发送")
                # return await self.bot.call_action(
                #     "send_group_forward_msg" if is_group else "send_private_forward_msg",
                #     group_id=event.group_id,
                #     messages=[
                #         MessageSegment.node_custom(event.self_id, "ChatGPT", resp)
                #     ]
                # )

        return respond

    def __init__(self, bot: CQHttp, transform_from_message_chain: Callable):
        self.bot = bot
        self.transform_from_message_chain = transform_from_message_chain
        self.directory = os.path.dirname(current_file_path)
        self.connstr = f"{self.directory}/database.db"
        self.conn = sqlite3.connect(f"{self.connstr}")
        self._initdb()
        # self.respond=_respond
        # 创建一个定时器，每5秒调用一次my_function函数 args: Iterable[Any]
        # self.timer = threading.Timer(10, function=auto_reply,args=[self.bot])
        # 启动定时器
        # self.timer.start()
        self.run_reply()

    def run_reply(self):
        # loop = asyncio.new_event_loop()
        # callback = partial(loop.run_until_complete,  lambda : auto_reply(self.bot,loop))
        timer = threading.Timer(
            5, function=auto_reply, args=[self.bot, self.transform_from_message_chain]
        )
        # timer = threading.Timer(5, callback)
        # timer = threading.Timer(10, function=auto_reply,args=[self.bot])
        timer.start()
        # loop.close()

    def _initdb(self):
        c = self.conn.cursor()
        try:
            c.execute("SELECT 1 FROM chatcache")
            c.fetchall()
        except Exception as e:
            logger.exception(e)
            c.execute(
                """CREATE TABLE chatcache 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            groupid text, 
                            userid text, 
                            nickname text,
                            date text,
                            messageid text,
                            content text)"""
            )
        c.close()
        self.conn.commit()

    def insert_chatcontent(
        self,
        groupid: str,
        userid: str,
        nickname: str,
        date: str,
        message_id: str,
        content: str,
    ):
        if content.find("CQ:record,file=") > 0:
            return
        c = self.conn.cursor()
        logger.debug(f"[ChatCache] {current_file_path}")
        try:
            if self.get_count_chatcontent(groupid) > 9:
                self.delete_first_chatcontent(groupid)
            pattern = r"\[CQ:reply,([^\]]+)\]"
            content = re.sub(pattern, "", content)
            # logger.debug(f"[ChatCache] insert_chatcontent：{groupid}-{userid}-{nickname}-{date}-{content}")
            c.execute(
                f"""INSERT INTO chatcache (groupid,userid,nickname,date,messageid,content) VALUES (
                            '{groupid}',
                            '{userid}' ,
                            '{nickname}' ,
                            '{date}' ,
                            "{message_id}",
                            '{content}' )"""
            )
        except Exception as e:
            logger.exception(e)
        self.conn.commit()
        c.close()

    def delete_first_chatcontent(self, groupid: str):
        c = self.conn.cursor()
        c.execute(
            f"""DELETE FROM chatcache
                        WHERE id = (SELECT MIN(id) FROM chatcache
                            WHERE groupid='{groupid}'
                        ) """
        )
        self.conn.commit()
        c.close()

    def delete_all_chatcontent(self, groupid: str):
        c = self.conn.cursor()
        c.execute(
            f"""DELETE FROM chatcache
                    WHERE groupid='{groupid}'
                    """
        )
        self.conn.commit()
        c.close()
    def delete_kepplast_chatcontent(self, groupid: str):
        c = self.conn.cursor()
        try:
            c.execute(
                f"""DELETE FROM chatcache
                        WHERE groupid='{groupid}'
                        AND datetime(strftime('%Y-%m-%d %H:%M:%f', date) < (
                            SELECT MAX(datetime(strftime('%Y-%m-%d %H:%M:%f', date)) ) 
                            FROM chatcache 
                            WHERE groupid='{groupid}'
                            )
                        """
            )
            self.conn.commit()
        except Exception as e:
            pass
        c.close()
    def get_groupids(self):
        groupids = []
        c = self.conn.cursor()
        c.execute(
            f"""SELECT DISTINCT groupid FROM chatcache group by groupid
                  """
        )
        results = c.fetchall()
        if len(results) > 0:
            for result in results:
                groupids.append(result[0])
                # content+=f"{result[3]}:{result[6]}\n"
        c.close()
        return groupids

    def select_chatcontent(self, groupid: str):
        content = ""
        c = self.conn.cursor()
        c.execute(
            f"""SELECT * FROM chatcache
                            WHERE groupid='{groupid}'
                            and datetime(strftime('%Y-%m-%d %H:%M:%f', date)) > datetime('now', '-480 seconds')
                        """
        )
        results = c.fetchall()
        if len(results) > 1:
            for result in results:
                content += f"{result[3]}:{result[6]}\n"
        c.close()
        return content

    def get_count_chatcontent(self, groupid: str):
        count = 0
        c = self.conn.cursor()
        myresult = c.execute(
            f"""SELECT count(id) FROM chatcache
                            WHERE groupid={groupid}
                        """
        )
        count = c.fetchone()[0]
        c.close()
        return count

    def get_aiJprompt(self, nickname: str, content: str):
        Judgereplyprompt = f"""
请根据下面的对话内容，判断最后一段发言内容是否是在对{nickname}说,并且最后一段发言内容不能是{nickname}说的，
如何是，就根据最后一段发言内容回复对应的内容。
如果不是，就直接回复"不需要回复"。下面是各个用户的发言内容--\n
{content}
    """
        return Judgereplyprompt

    def get_aiJprompt2(self, nickname: str, content: str):
        Judgereplyprompt = f"""
请根据下面的对话内容，判断是否有需要解决的问题,
如果有，就回复你对问题的详细看法，越详细越好。
如果没有，就直接回复"不需要回复"。
下面是各个用户的发言内容--\n
{content}
    """
        return Judgereplyprompt

    def __del__(self):
        self.conn.commit()
        self.conn.close()

    async def ask(self, group_id: str, prompt: str) -> Generator[str, None, None]:
        session_id = f"group-{group_id}"
        # prompt=""
        conversation_handler = await ConversationHandler.get_handler(session_id)
        if not conversation_handler.current_conversation:
            conversation_handler.current_conversation = (
                await conversation_handler.create(config.response.default_ai)
            )
            # ask(prompt=prompt, chain=chain, name=nickname)
        task = conversation_handler.current_conversation.ask(prompt=prompt, name="")
        async for rendered in task:
            if rendered:
                # logger.debug(f"conversation_context.ask,{rendered}")
                if not str(rendered).strip():
                    logger.warning("检测到内容为空的输出，已忽略")
                    continue
                event = Event()
                # event.sender=''
                # event.user_id=''
                event.group_id = group_id
                event.self_id = str(config.onebot.qq)
                # logger.debug(f"ai:\n{str(rendered)}")
                yield str(rendered)
                # await self.respond(event,rendered)

    async def respond(self, event, msg: str):
        # _respond: Callable

        _respond = self.response(event, True)
        ret = await _respond(msg)
        return


def auto_reply(bot: CQHttp, transform_from_message_chain: Callable):
    async def thread_async_function():
        chatche = ChatCache(bot, transform_from_message_chain)
        # ,session_id: str f"group-{event.group_id}"
        print("Prepare for automatic reply......")
        groupids = chatche.get_groupids()
        for groupid in groupids:
            chatcontent = chatche.select_chatcontent(groupid)
            logger.debug(f"获得群 {groupid} 的聊天内容:\n{chatcontent}")
            if chatcontent == "":
                continue

            ####回复针对自己的话
            aiJprompt = chatche.get_aiJprompt(
                f"bot-{str(config.onebot.qq)}", chatcontent
            )
            logger.debug(f"aiJprompt:\n{aiJprompt}")
            repliedflag=0
            replycontent=''
            async for value in chatche.ask(groupid, aiJprompt):
                logger.debug(f"ai1:\n{value}")
                if value.find("不需要回复") > -1:
                    # task.cancel()
                    continue
                # if value.find("是的") > 0:
                # async for value2 in chatche.ask(groupid,"根据前面对话内容的最后一次发言内容回复"):
                #     logger.debug(f"{value2}")
                event = Event()
                # event.sender=''
                # event.user_id=''
                event.group_id = groupid
                # event.self_id = str(config.onebot.qq)
                # 清除并回复
                chatche.delete_all_chatcontent(groupid)
                # chatche.delete_kepplast_chatcontent(groupid)
                pattern = r"\[CQ:reply,([^\]]+)\]"
                value = re.sub(pattern, "", value)
                logger.debug(f"ai2:\n{value}")
                await chatche.respond(event, value)
                repliedflag=1
                replycontent=value

            ####回复需要帮助的话
            aiJprompt2 = chatche.get_aiJprompt2(
                f"bot-{str(config.onebot.qq)}", chatcontent
            )
            logger.debug(f"aiJprompt2:\n{aiJprompt2}")
            async for value2 in chatche.ask(groupid, aiJprompt2):
                logger.debug(f"ai2:\n{value2}")
                if value2.find("不需要回复") > -1:
                    # task.cancel()
                    continue
                # if value.find("是的") > 0:
                # async for value2 in chatche.ask(groupid,"根据前面对话内容的最后一次发言内容回复"):
                #     logger.debug(f"{value2}")
                event = Event()
                # event.sender=''
                # event.user_id=''
                event.group_id = groupid
                # event.self_id = str(config.onebot.qq)
                # 清除并回复
                chatche.delete_all_chatcontent(groupid)
                # chatche.delete_kepplast_chatcontent(groupid)
                pattern = r"\[CQ:reply,([^\]]+)\]"
                value2 = re.sub(pattern, "", value2)
                logger.debug(f"ai2:\n{value2}")
                await chatche.respond(event, value2)
                repliedflag=1
                replycontent=value2
            
            # if repliedflag==1:
            #     curtime = datetime.now()
            #     chatche.insert_chatcontent(
            #         groupid,
            #         str(config.onebot.qq),
            #         f"bot-{str(config.onebot.qq)}",
            #         curtime.strftime("%Y-%m-%d %H:%M:%S"),
            #         str(0),
            #         replycontent,
            #     )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(thread_async_function())
    finally:
        loop.close()
