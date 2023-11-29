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
from .dbmng import DB_Manager

config = Config.load_config()
current_file_path = os.path.abspath(sys.argv[0])


class Smart_Response():
    """ """

    def __init__(self, bot: CQHttp=None, transform_from_message_chain: Callable=None):
        self.bot = bot
        self.transform_from_message_chain = transform_from_message_chain
        self.directory = os.path.dirname(current_file_path)
        self.connstr = f"{self.directory}/database.db"
        self.conn = sqlite3.connect(f"{self.connstr}")
        self.db_manager=DB_Manager()
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

    async def ask(self, group_id: str, prompt: str) -> Generator[str, None, None]:
        session_id = f"group-{group_id}"
        # prompt=""
        conversation_handler = await ConversationHandler.get_handler(session_id)
        if not conversation_handler.current_conversation:
            conversation_handler.current_conversation = (
                await conversation_handler.create(config.response.default_ai)
            )
            # ask(prompt=prompt, chain=chain, name=nickname)
        # last_conversation_id=conversation_handler.current_conversation.adapter.conversation_id
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
            logger.debug(f"[Smart_Response] 尝试发送消息：{str(resp)}")
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
        event.message_id=self.db_manager.get_last_messageid(event.group_id)
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
        nonlocal no_response_required
        async for val in chatche.ask(groupid, aiJprompt):
            logger.debug(f"ai1:\n{val}")
            value = val
            if value.find("不需要回复") > -1:
                no_response_required+=1
                if no_response_required>2:
                    # 清除
                    chatche.db_manager.delete_all_chatcontent(groupid)
                continue
            no_response_required=0
            event = Event()
            # event.sender=''
            # event.user_id=''
            event.group_id = groupid
            # event.self_id = str(config.onebot.qq)
            # 清除并回复
            chatche.db_manager.delete_all_chatcontent(groupid)
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
            pattern = rf"{str(config.onebot.qq)}:"
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
        groupids = chatche.db_manager.get_groupids()
        for groupid in groupids:
            chatcontent = chatche.db_manager.select_chatcontent(groupid)
            if chatcontent == "":
                await asyncio.sleep(1)
                continue
            logger.debug(f"获得群 {groupid} 的聊天内容:\n{chatcontent}")

            ####回复针对自己的话
            # aiJprompt = chatche.get_aiJprompt(
            #     f"bot-{str(config.onebot.qq)}", chatcontent
            # )
            # await reply1(chatche, groupid, aiJprompt)

            ####回复需要帮助的话
            aiJprompt3 = chatche.db_manager.get_aiJprompt3(
                f"bot-{str(config.onebot.qq)}", chatcontent
            )
            await reply1(chatche, groupid, aiJprompt3)
        await asyncio.sleep(15)
    try:
        # event = asyncio.Event()
        while True:
            try:
                loop.run_until_complete(thread_async_function())
                
                # time.sleep(15)
            except Exception as e:
                logger.exception(e)
                time.sleep(15)
                pass
    finally:
        loop.close()
    # chatche.run_reply()
