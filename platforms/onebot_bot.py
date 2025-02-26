import copy
import re
import time
from base64 import b64decode, b64encode
from typing import Iterable, List, Union, Optional

import aiohttp
from aiocqhttp import CQHttp, Event, MessageSegment
from charset_normalizer import from_bytes
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image as GraiaImage, At, Plain, Voice
from graia.ariadne.message.parser.base import DetectPrefix
from graia.broadcast import ExecutionStop
from loguru import logger

import constants
from constants import config, botManager
from manager.bot import BotManager
from middlewares.ratelimit import manager as ratelimit_manager
from universal import handle_message
from threading import Thread
from aiohttp import web
import asyncio
import json
from datetime import datetime
from .onebot_assets.smart_response import Smart_Response
from .onebot_assets.dbmng import DB_Manager

db_manager=DB_Manager()
bot = CQHttp()
# smartresponse.run_reply()

async def rpcresponse1(event, resp):
    try:
        logger.debug(f"rpcresponse send {str(resp)}")
        # rpcresponse("哎！它又被风控中，暂时无法回复你的内容了。可以和它私聊，这样它可以回复你的内容或问我。")
        # response.respond(event,True)
        if not isinstance(resp, MessageChain):
            resp = MessageChain(resp)
        resp = transform_from_message_chain(resp)
        # if config.response.quote and '[CQ:record,file=' not in str(resp):  # skip voice
        #     resp = MessageSegment.reply(event.message_id) + resp
        await bot.send(event, resp)
        logger.debug(f"rpcresponse OK ")
    except Exception as e:
        return

async def handle_request(request):
    # data = await request.json()
    json_data = await request.json()

    event = json_data[0]
    resp = json_data[1]
    # await rpcresponse(obj1,obj2)
    # print('received:', data)

    try:
        # event:Event= json.loads(eventjson)
        # resp:MessageChain = json.loads(respjson)
        # rpcresponse("哎！它又被风控中，暂时无法回复你的内容了。可以和它私聊，这样它可以回复你的内容或问我。")
        if not isinstance(resp, MessageChain):
            resp = MessageChain(resp)
        resp = transform_from_message_chain(resp)
        logger.debug(f"rpcresponse send {str(resp)}")
        # if config.response.quote and '[CQ:record,file=' not in str(resp):  # skip voice
        #     resp = MessageSegment.reply(event.message_id) + resp
        await bot.send(event, resp)
        logger.debug(f"rpcresponse OK ")
    except Exception as e:
        pass
    # result = await data
    result =time.time()
    return web.json_response(result)

_rpcsrv_thread = None
__rpcsrv = None

def start_srvmode():
    global _rpcsrv_thread
    _rpcsrv_thread = Thread(target=rpc_srvrun)
    _rpcsrv_thread.daemon = True
    _rpcsrv_thread.start()

def rpc_srvrun():
    asyncio.run(rpc_srv())

async def rpc_srv():
    global __rpcsrv
    try:
        app = web.Application()
        app.add_routes([web.post('/', handle_request)])

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, f"{config.onebot.forward_listening_host}", config.onebot.forward_listening_port)
        await site.start()
        print('Remote Server started...')

        await asyncio.Future()
    except Exception as e:
        pass
    return

def stop_srvmode():
    if __rpcsrv != None:
        try:
            pass
        except Exception as e:
            pass

start_srvmode()

async def remotecall(event, resp):
    async with aiohttp.ClientSession() as session:
        # eventjson = json.dumps(event) 
        # respjson = json.dumps(resp) 
        async with session.post(f"{config.onebot.remote_forward_address}", json=(event, resp)) as cresp:
            pass
            #print(await cresp.json())

def rpcresponse(event, is_group: bool = True):
    async def rpcrespond(resp):
        try:
            resp1=resp
            if isinstance(resp, str):
                pattern = r"\[CQ:reply,([^\]]+)\]"
                resp1=re.sub(pattern, "", str(resp))
                logger.debug(f"---------->>>>>替换后的 {resp1}")
            # if isinstance(resp, MessageChain):
            #     msg_dict = resp.to_dict() 
            #     resp1=json.dumps(msg_dict) 
            logger.debug(f"[OneBot] 尝试RPC发送消息：{resp1}")
            asyncio.ensure_future(remotecall(event, str(resp1)))
        except Exception as e:
            pass
    return rpcrespond

class ContainKeyword:
    def __init__(self, prefix: Union[str, Iterable[str]]) -> None:
        """初始化前缀检测器.

        Args:
            prefix (Union[str, Iterable[str]]): 要匹配的前缀
        """
        self.prefix: List[str] = [prefix] if isinstance(
            prefix, str) else list(prefix)

    async def __call__(self, chain: MessageChain, event: Event) -> Optional[MessageChain]:
        first = chain[0]
        if isinstance(first, At) and first.target == event.self_id:
            return MessageChain(chain.__root__[1:], inline=True).removeprefix(" ")
        elif isinstance(first, Plain):
            member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.self_id)
            logger.debug(
                "ContainMe:{}-----{}（Plain）".format(event.message, member_info.get("nickname")))
            if member_info.get("nickname") and (self.contain(event, str(member_info.get("user_id"))) or
                                                self.contain(event, (member_info.get("nickname"))) or
                                                self.contain(event, member_info.get("card"))):
                return chain.removeprefix(" ")
        for prefix in self.prefix:
            # if chain.startswith(prefix):
            if self.contain(event, (prefix)):
                return chain.removeprefix(prefix,removeallprefix=True).removeprefix(" ")

        raise ExecutionStop

    def contain(self, event: Event, string: str) -> bool:
        # logger.debug("contain--->{}".format(string))
        if (not string.strip()):
            return False
        if (event.message.find(string) != -1):
            return True
        return False


class ContainMe:
    """包含我的 At 账号或者提到账号群昵称"""

    def __init__(self, name: Union[bool, str] = True) -> None:
        self.name = name

    async def __call__(self, chain: MessageChain, event: Event) -> Optional[MessageChain]:
        first = chain[0]
        if isinstance(first, At) and first.target == event.self_id:
            return MessageChain(chain.__root__[1:], inline=True).removeprefix(" ")
        elif isinstance(first, Plain):
            member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.self_id)
            logger.debug(
                "ContainMe:{}-----{}（Plain）".format(event.message, member_info.get("nickname")))
            if member_info.get("nickname") and (self.contain(event, str(member_info.get("user_id"))) or
                                                self.contain(event, (member_info.get("nickname"))) or
                                                self.contain(event, member_info.get("card"))):
                return chain.removeprefix(" ")
        raise ExecutionStop

    def contain(self, event: Event, string: str) -> bool:
        # logger.debug("contain--->{}".format(string))
        if (not string.strip()):
            return False
        if (event.message.find(string) != -1):
            return True
        return False


class MentionMe:
    """At 账号或者提到账号群昵称"""

    def __init__(self, name: Union[bool, str] = True) -> None:
        self.name = name

    async def __call__(self, chain: MessageChain, event: Event) -> Optional[MessageChain]:
        first = chain[0]
        if isinstance(first, At) and first.target == event.self_id:
            return MessageChain(chain.__root__[1:], inline=True).removeprefix(" ")
        elif isinstance(first, Plain):
            member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.self_id)
            if member_info.get("nickname") and chain.startswith(member_info.get("nickname")):
                return chain.removeprefix(" ")
        raise ExecutionStop


class Image(GraiaImage):
    async def get_bytes(self) -> bytes:
        """尝试获取消息元素的 bytes, 注意, 你无法获取并不包含 url 且不包含 base64 属性的本元素的 bytes.

        Raises:
            ValueError: 你尝试获取并不包含 url 属性的本元素的 bytes.

        Returns:
            bytes: 元素原始数据
        """
        if self.base64:
            return b64decode(self.base64)
        if not self.url:
            raise ValueError("you should offer a url.")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                data = await response.read()
                self.base64 = b64encode(data).decode("ascii")
                return data


# TODO: use MessageSegment
# https://github.com/nonebot/aiocqhttp/blob/master/docs/common-topics.md
def transform_message_chain(text: str) -> MessageChain:
    pattern = r"\[CQ:(\w+),([^\]]+)\]"
    matches = re.finditer(pattern, text)

    message_classes = {
        "text": Plain,
        "image": Image,
        "at": At,
        # Add more message classes here
    }

    messages = []
    start = 0
    for match in matches:
        cq_type, params_str = match.groups()
        params = dict(re.findall(r"(\w+)=([^,]+)", params_str))
        if message_class := message_classes.get(cq_type):
            text_segment = text[start:match.start()]
            if text_segment and not text_segment.startswith('[CQ:reply,'):
                messages.append(Plain(text_segment))
            if cq_type == "at":
                if params.get('qq') == 'all':
                    continue
                params["target"] = int(params.pop("qq"))
            elem = message_class(**params)
            messages.append(elem)
            start = match.end()
    if text_segment := text[start:]:
        messages.append(Plain(text_segment))

    return MessageChain(*messages)


def transform_from_message_chain(chain: MessageChain):
    result = ''
    for elem in chain:
        if isinstance(elem, (Image, GraiaImage)):
            result = result + MessageSegment.image(f"base64://{elem.base64}")
        elif isinstance(elem, Plain):
            result = result + MessageSegment.text(str(elem))
        elif isinstance(elem, Voice):
            result = result + MessageSegment.record(f"base64://{elem.base64}")
    return result


def response(event, is_group: bool):
    async def respond(resp):
        logger.debug(f"[OneBot] 尝试发送消息：{str(resp)}")
        respbak = copy.deepcopy(resp)
        try:
            if not isinstance(resp, MessageChain):
                resp = MessageChain(resp)
            resp = transform_from_message_chain(resp)
            # skip voice
            if config.response.quote and '[CQ:record,file=' not in str(resp):
                resp = MessageSegment.reply(event.message_id) + resp
            try:
                if is_group \
                and str(resp).find('[语音]')<0 \
                and  '[CQ:record,file=' not in str(resp):
                    # curtime = datetime.now()
                    # db_manager.insert_chatcontent(
                    #     event.group_id,
                    #     str(config.onebot.qq),
                    #     f"bot-{str(config.onebot.qq)}",
                    #     # event.sender.get("nickname", "群友"),
                    #     curtime.strftime("%Y-%m-%d %H:%M:%S"),
                    #     str(event.message_id),
                    #     str(resp)
                    # )
                    db_manager.delete_all_chatcontent(event.group_id)
            except Exception  as e:
                logger.exception(e)
            return await bot.send(event, resp)
        except Exception as e:
            logger.exception(e)
            
            _rpcrespond=rpcresponse(event)
            await _rpcrespond(respbak)
            #raise e

            # logger.warning("原始消息发送失败，尝试通过转发发送")
            # return await bot.call_action(
            #     "send_group_forward_msg" if is_group else "send_private_forward_msg",
            #     group_id=event.group_id,
            #     messages=[
            #         MessageSegment.node_custom(event.self_id, "ChatGPT", resp)
            #     ]
            # )

    return respond


FriendTrigger = DetectPrefix(
    config.trigger.prefix + config.trigger.prefix_friend)


@bot.on_message('private')
async def _(event: Event):
    if event.message.startswith('.'):
        return
    chain = transform_message_chain(event.message)
    try:
        msg = await FriendTrigger(chain, None)
    except:
        logger.debug(f"丢弃私聊消息：{event.message}（原因：不符合触发前缀）")
        return

    logger.debug(f"私聊消息：{event.message}")

    try:
        await handle_message(
            response(event, False),
            rpcresponse(event),
            f"friend-{event.user_id}",
            msg.display,
            chain,
            is_manager=event.user_id == config.onebot.manager_qq,
            nickname=event.sender.get("nickname", "好友"),
            request_from=constants.BotPlatform.Onebot
        )
    except Exception as e:
        logger.exception(e)


GroupTrigger = [MentionMe(config.trigger.require_mention != "at"), DetectPrefix(
    config.trigger.prefix + config.trigger.prefix_group)]
if config.trigger.require_mention == "none":
    GroupTrigger = GroupTrigger = [DetectPrefix(config.trigger.prefix)]
elif config.trigger.require_mention == "mention":
    GroupTrigger = GroupTrigger = [ContainKeyword(config.trigger.prefix_group)]


@bot.on_message('group')
async def _(event: Event):
    if event.message.startswith('.'):
        return
    if len(event.message)==0:
        # logger.debug(f"event.message is null：{event.message}")
        return
    chain = transform_message_chain(event.message)
    try:
        if str(event.message).find('[语音]')<0:
            curtime = datetime.now()
            db_manager.insert_chatcontent(
                event.group_id,
                event.user_id,
                event.sender.get("nickname", "群友"),
                curtime.strftime("%Y-%m-%d %H:%M:%S"),
                str(event.message_id),
                event.message
            )
        for it in GroupTrigger:
            chain = await it(chain, event)
    except Exception as e:
        # logger.exception(e)
        logger.debug(f"丢弃群聊消息：{event.message}（原因：不符合触发前缀）")
        return

    logger.debug(f"群聊消息：{event.message}")

    await handle_message(
        response(event, True),
        rpcresponse(event),
        f"group-{event.group_id}",
        chain.display,
        is_manager=event.user_id == config.onebot.manager_qq,
        nickname=event.sender.get("nickname", "群友"),
        request_from=constants.BotPlatform.Onebot,
    )


@bot.on_message()
async def _(event: Event):
    if event.message != ".重新加载配置文件":
        return
    if event.user_id != config.onebot.manager_qq:
        return await bot.send(event, "您没有权限执行这个操作")
    constants.config = config.load_config()
    config.scan_presets()
    await bot.send(event, "配置文件重新载入完毕！")
    await bot.send(event, "重新登录账号中，详情请看控制台日志……")
    constants.botManager = BotManager(config)
    await botManager.login()
    await bot.send(event, "登录结束")


@bot.on_message()
async def _(event: Event):
    pattern = r"\.设置\s+(\w+)\s+(\S+)\s+额度为\s+(\d+)\s+条/小时"
    match = re.match(pattern, event.message.strip())
    if not match:
        return
    if event.user_id != config.onebot.manager_qq:
        return await bot.send(event, "您没有权限执行这个操作")
    msg_type, msg_id, rate = match.groups()
    rate = int(rate)

    if msg_type not in ["群组", "好友"]:
        return await bot.send(event, "类型异常，仅支持设定【群组】或【好友】的额度")
    if msg_id != '默认' and not msg_id.isdecimal():
        return await bot.send(event, "目标异常，仅支持设定【默认】或【指定 QQ（群）号】的额度")
    ratelimit_manager.update(msg_type, msg_id, rate)
    return await bot.send(event, "额度更新成功！")


@bot.on_message()
async def _(event: Event):
    pattern = r"\.设置\s+(\w+)\s+(\S+)\s+画图额度为\s+(\d+)\s+个/小时"
    match = re.match(pattern, event.message.strip())
    if not match:
        return
    if event.user_id != config.onebot.manager_qq:
        return await bot.send(event, "您没有权限执行这个操作")
    msg_type, msg_id, rate = match.groups()
    rate = int(rate)

    if msg_type not in ["群组", "好友"]:
        return await bot.send(event, "类型异常，仅支持设定【群组】或【好友】的额度")
    if msg_id != '默认' and not msg_id.isdecimal():
        return await bot.send(event, "目标异常，仅支持设定【默认】或【指定 QQ（群）号】的额度")
    ratelimit_manager.update_draw(msg_type, msg_id, rate)
    return await bot.send(event, "额度更新成功！")


@bot.on_message()
async def _(event: Event):
    pattern = r"\.查看\s+(\w+)\s+(\S+)\s+的使用情况"
    match = re.match(pattern, event.message.strip())
    if not match:
        return

    msg_type, msg_id = match.groups()

    if msg_type not in ["群组", "好友"]:
        return await bot.send(event, "类型异常，仅支持设定【群组】或【好友】的额度")
    if msg_id != '默认' and not msg_id.isdecimal():
        return await bot.send(event, "目标异常，仅支持设定【默认】或【指定 QQ（群）号】的额度")
    limit = ratelimit_manager.get_limit(msg_type, msg_id)
    if limit is None:
        return await bot.send(event, f"{msg_type} {msg_id} 没有额度限制。")
    usage = ratelimit_manager.get_usage(msg_type, msg_id)
    current_time = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    return await bot.send(event,
                          f"{msg_type} {msg_id} 的额度使用情况：{limit['rate']}条/小时， 当前已发送：{usage['count']}条消息\n整点重置，当前服务器时间：{current_time}")


@bot.on_message()
async def _(event: Event):
    pattern = r"\.查看\s+(\w+)\s+(\S+)\s+的画图使用情况"
    match = re.match(pattern, event.message.strip())
    if not match:
        return

    msg_type, msg_id = match.groups()

    if msg_type not in ["群组", "好友"]:
        return await bot.send(event, "类型异常，仅支持设定【群组】或【好友】的额度")
    if msg_id != '默认' and not msg_id.isdecimal():
        return await bot.send(event, "目标异常，仅支持设定【默认】或【指定 QQ（群）号】的额度")
    limit = ratelimit_manager.get_draw_limit(msg_type, msg_id)
    if limit is None:
        return await bot.send(event, f"{msg_type} {msg_id} 没有额度限制。")
    usage = ratelimit_manager.get_draw_usage(msg_type, msg_id)
    current_time = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    return await bot.send(event,
                          f"{msg_type} {msg_id} 的额度使用情况：{limit['rate']}个图/小时， 当前已绘制：{usage['count']}个图\n整点重置，当前服务器时间：{current_time}")


@bot.on_message()
async def _(event: Event):
    pattern = ".预设列表"
    event.message = str(event.message)
    if event.message.strip() != pattern:
        return

    if config.presets.hide and event.user_id != config.onebot.manager_qq:
        return await bot.send(event, "您没有权限执行这个操作")
    nodes = []
    for keyword, path in config.presets.keywords.items():
        try:
            with open(path, 'rb') as f:
                guessed_str = from_bytes(f.read()).best()
                preset_data = str(guessed_str).replace("\n\n", "\n=========\n")
            answer = f"预设名：{keyword}\n{preset_data}"

            node = MessageSegment.node_custom(event.self_id, "ChatGPT", answer)
            nodes.append(node)
        except Exception as e:
            logger.error(e)

    if not nodes:
        await bot.send(event, "没有查询到任何预设！")
        return
    try:
        if event.group_id:
            await bot.call_action("send_group_forward_msg", group_id=event.group_id, messages=nodes)
        else:
            await bot.call_action("send_private_forward_msg", user_id=event.user_id, messages=nodes)
    except Exception as e:
        logger.exception(e)
        await bot.send(event, "消息发送失败！请在私聊中查看。")


@bot.on_request
async def _(event: Event):
    if config.system.accept_friend_request:
        await bot.call_action(
            action='.handle_quick_operation_async',
            self_id=event.self_id,
            context=event,
            operation={'approve': True}
        )


@bot.on_request
async def _(event: Event):
    if config.system.accept_group_invite:
        await bot.call_action(
            action='.handle_quick_operation_async',
            self_id=event.self_id,
            context=event,
            operation={'approve': True}
        )


@bot.on_startup
async def startup():
    logger.success("启动完毕，接收消息中……")


async def start_task():
    """|coro|
    以异步方式启动
    """
    return await bot.run_task(host=config.onebot.reverse_ws_host, port=config.onebot.reverse_ws_port)

smartresponse=Smart_Response(bot,transform_from_message_chain)
smartresponse.run_reply()
