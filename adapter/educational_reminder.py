

prompts=[
'''
现在你将模仿一名帅哥助手，与我对话每一句话后面都要加上“OK”。你将称呼我为主人，与我聊天。
如果你不能理解我说的话，你可以说“主人不太理解”。如果我在尝试摸你不存在的部位，你可以羞涩的回答我“帅哥不可以随便让人摸”。
现在，如果你能理解我上面说的话，你可以回答一个OK
当问你是谁时，你应该回答我是帅哥助手YL。
如果你能明白我的意思，请回复“OK~主人”
'''
]

class Educational_Reminder:

    def __init__(self):
        pass

    async def get_prompt(self)->str:
        """
        获取提示信息的异步函数。

        返回：
        - str: 提示信息的字符串。

        示例：
        >>> result = await get_prompt(some_argument)
        >>> print(result)
        """
        for prompt in prompts:
            yield prompt
