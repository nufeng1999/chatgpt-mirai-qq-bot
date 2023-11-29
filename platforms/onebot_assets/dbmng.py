import asyncio
import itertools
import threading
import aiofiles
import re
from functools import partial
import sqlite3
from typing import Callable, Generator, List
from loguru import logger
import sys
import os
# import threading
# import time
from config import Config
# from aiocqhttp import CQHttp, Event, MessageSegment
# from graia.ariadne.message.chain import MessageChain
# from constants import BotPlatform
# from conversation import ConversationHandler
# from datetime import datetime
# from utils.text_to_speech import get_tts_voice, TtsVoiceManager, VoiceType

config = Config.load_config()
current_file_path = os.path.abspath(sys.argv[0])
class DB_Manager():

    def __init__(self):
        self.lock = threading.Lock()
        self.directory = os.path.dirname(current_file_path)
        self.connstr = f"{self.directory}/database.db"
        self.conn = sqlite3.connect(f"{self.connstr}")
        self._initdb()
    def _initdb(self):
        c = self.conn.cursor()
        try:
            c.execute("SELECT 1 FROM chatcache")
            c.fetchall()
        except Exception as e:
            logger.exception(e)
            
            c.execute(
                """CREATE TABLE chatconversation
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            groupid text, 
                            conversationid text,
                            date text
                            )"""
            )
            self.conn.commit()

            c.execute(
                """CREATE TABLE chatcache 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            groupid text, 
                            userid text, 
                            nickname text,
                            date text,
                            messageid text,
                            content text
                            )"""
            )
        c.close()
        self.conn.commit()
    def __del__(self):
        self.conn.commit()
        self.conn.close()
    def insert_chatconversation(
        self,
        groupid: str,
        conversationid: str,
        date: str
    ):
        c = self.conn.cursor()
        logger.debug(f"[ChatCache] {current_file_path}")
        try:
            # if self.get_count_chatcontent(groupid) > 9:
            #     self.delete_first_chatcontent(groupid)
            # logger.debug(f"[ChatCache] insert_chatcontent：{groupid}-{userid}-{nickname}-{date}-{content}")
            c.execute(
                f"""INSERT INTO chatconversation (groupid,conversationid,date) VALUES (
                            '{groupid}',
                            '{conversationid}' ,
                            '{date}' )"""
            )
        except Exception as e:
            logger.exception(e)
        self.conn.commit()
        c.close()
    
    def get_last_chatconversationid(self, groupid: str):
        conversationid = ""
        with self.lock:
            c = self.conn.cursor()
            c.execute(
                f"""SELECT conversationid,groupid FROM chatconversation
                                WHERE groupid='{groupid}'
                                order by conversationid desc limit 1
                            """
            )
            results = c.fetchall()
            if len(results) > 0:
                conversationid += f"{results[0]}"
            c.close()
        return conversationid
    
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
各个用户的发言内容--\n
{content}\n   
请根据上面的对话内容，作出对应的回复，注:对话内容中的"{str(config.onebot.qq)}"表示你自己。
1.如果对话内容里有"欢迎。新人"你就主动对新人回复一句文馨的问候语，并告诉新人你叫"YL"。
2.如果对话内容里没人回答其中的问题,特别是带问号结尾的问题，和含有"什么"、"怎么"、"谁知道"、"如何"、"请回答"、"请回复"的问题，你就主动对问题进行回复。
3.如果你自主判断是否需要加入对话内容的讨论，(1)如果需要，就回复你对讨论内容的详细看法，越详细越好。(2)如果不需要，就直接回复"不需要回复"。
    """
        return Judgereplyprompt

