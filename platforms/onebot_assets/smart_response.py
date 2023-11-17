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
import time
from config import Config
from aiocqhttp import CQHttp, Event, MessageSegment
from graia.ariadne.message.chain import MessageChain
from constants import BotPlatform
from conversation import ConversationHandler
from datetime import datetime
from utils.text_to_speech import get_tts_voice, TtsVoiceManager, VoiceType

config = Config.load_config()
current_file_path = os.path.abspath(sys.argv[0])


class Smart_Response():
    """ """

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
        # self.run_reply()

    def run_reply(self):
        # loop = asyncio.new_event_loop()
        # callback = partial(loop.run_until_complete,  lambda : auto_reply(self.bot,loop))
        timer = threading.Timer(
            15, function=auto_reply, args=[self.bot, self.transform_from_message_chain]
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
    def get_last_messageid(self, groupid: str):
        messageid = ""
        c = self.conn.cursor()
        c.execute(
            f"""SELECT messageid FROM chatcache
                            WHERE groupid='{groupid}'
                            and datetime(strftime('%Y-%m-%d %H:%M:%f', date)) > datetime('now', '-480 seconds')
                            order by id desc limit 1
                        """
        )
        results = c.fetchall()
        if len(results) > 0:
            messageid += f"{results[0]}"
        c.close()
        return messageid
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
        if len(results) > 0:
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

    def get_aiJprompt3(self, nickname: str, content: str):
        Judgereplyprompt = f"""
请根据下面的对话内容，对话内容中的"{str(config.onebot.qq)}"表示你自己。
如果对话内容里有"欢迎。新人",你就主动对新人回复一句文馨的问候语，并告诉新人你叫"YL"。
如果对话内容里没人回答其中的问题,特别是带问号结尾的问题，你就主动对问题进行回复。
判断是否需要加入对话内容的讨论。
如果需要，就回复你对讨论内容的详细看法，越详细越好。
如果不需要，就直接回复"不需要回复"。
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
                # logger.debug(f"rendered:\n{str(rendered)}")
                yield str(rendered)
                # await self.respond(event,rendered)

    def response(self, event, is_group: bool):
        async def respond(resp):
            logger.debug(f"[OneBot] 尝试发送消息：{str(resp)}")
            try:
                if not isinstance(resp, MessageChain):
                    resp = MessageChain(resp)
                resp = self.transform_from_message_chain(resp)
                # skip voice
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

    async def respond(self, event, msg: str):
        # _respond: Callable
        event.message_id=self.get_last_messageid(event.group_id)
        _respond = self.response(event, True)
        ret = await _respond(msg)
        # TTS Converting
        if not isinstance(msg, MessageChain):
            resp = MessageChain(msg)
        request_from=BotPlatform.Onebot
        session_id = f"group-{event.group_id}"
        conversation_handler = await ConversationHandler.get_handler(session_id)
        if not conversation_handler.current_conversation:
            conversation_handler.current_conversation = (
                await conversation_handler.create(config.response.default_ai)
            )
        
        # logger.debug(f"TTS Converting {conversation_handler.current_conversation.conversation_voice}")
        conversation_context=conversation_handler.current_conversation
        if conversation_context.conversation_voice and isinstance(resp, MessageChain):

            if request_from in [BotPlatform.Onebot, BotPlatform.AriadneBot]:
                voice_type = VoiceType.Silk
            elif request_from == BotPlatform.HttpService:
                voice_type = VoiceType.Mp3
            else:
                voice_type = VoiceType.Wav
            tasks = []
            for elem in resp:
                task = asyncio.create_task(get_tts_voice(elem, conversation_context, voice_type))
                tasks.append(task)
            while tasks:
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for voice_task in done:
                    voice = await voice_task
                    if voice:
                        # logger.debug(f"send voice... ")
                        await _respond(voice)
        return



def auto_reply(bot: CQHttp, transform_from_message_chain: Callable):
    chatche = Smart_Response(bot, transform_from_message_chain)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    no_response_required = 0

    def replace_line_starting_with(original_text, keyword, new_line):
        # 使用正则表达式匹配以关键字开头的整行
        pattern = re.compile(r"^" + re.escape(keyword) + r".*", re.MULTILINE)
        match = re.search(pattern, original_text)

        if match:
            # 找到匹配的行，替换为新的一行
            start, end = match.span()
            new_text = original_text[:start] + new_line + original_text[end:]
            return new_text
        else:
            # 如果没有找到匹配的行，返回原始文本
            return original_text

    async def reply1(chatche, groupid, aiJprompt):
        async for val in chatche.ask(groupid, aiJprompt):
            # logger.debug(f"ai1:\n{value}")
            value = val
            if value.find("不需要回复") > -1:
                no_response_required+=1
                if no_response_required>2:
                    # 清除
                    chatche.delete_all_chatcontent(groupid)
                continue
            no_response_required=0
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

            pattern = r"作为一个认知智能模型，"
            value = re.sub(pattern, "", value)
            pattern = r"需要 回复。"
            value = re.sub(pattern, "", value)
            pattern = r"根据上述对话内容，我认为需要加入讨论。"
            value = re.sub(pattern, "", value)
            pattern = r"我认为这个话题需要加入讨论。"
            value = re.sub(pattern, "", value)
            pattern = r"我认为这是一个值得讨论的话题。"
            value = re.sub(pattern, "", value)
            pattern = rf"{str(config.onebot.qq)}:"
            value = re.sub(pattern, "", value)
            pattern = rf"{str(config.onebot.qq)}"
            value = re.sub(pattern, "", value)
            pattern = rf"YL:"
            value = re.sub(pattern, "", value)
            

            keyword = "根据对话内容"
            new_line = ""
            result = replace_line_starting_with(value, keyword, new_line)
            result = replace_line_starting_with(result, "需要回复", new_line)
            result = replace_line_starting_with(result, "是的，需要解决这个问题", new_line)
            result = replace_line_starting_with(result, "根据提供的对话内容", new_line)
            result = replace_line_starting_with(result, "需要加入讨论", new_line)
            result = replace_line_starting_with(result, "当前无法回答", new_line)

            await chatche.respond(event, result)

    async def thread_async_function():
        # ,session_id: str f"group-{event.group_id}"
        print("Prepare for automatic reply......")
        groupids = chatche.get_groupids()
        for groupid in groupids:
            chatcontent = chatche.select_chatcontent(groupid)
            logger.debug(f"获得群 {groupid} 的聊天内容:\n{chatcontent}")
            if chatcontent == "":
                continue

            ####回复针对自己的话
            # aiJprompt = chatche.get_aiJprompt(
            #     f"bot-{str(config.onebot.qq)}", chatcontent
            # )
            # await reply1(chatche, groupid, aiJprompt)

            ####回复需要帮助的话
            aiJprompt3 = chatche.get_aiJprompt3(
                f"bot-{str(config.onebot.qq)}", chatcontent
            )
            await reply1(chatche, groupid, aiJprompt3)
        await asyncio.sleep(7)
    try:
        # event = asyncio.Event()
        while True:
            try:
                loop.run_until_complete(thread_async_function())
                
                # time.sleep(15)
            except Exception as e:
                pass
    finally:
        loop.close()
    # chatche.run_reply()
