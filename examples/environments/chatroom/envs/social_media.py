# -*- coding: utf-8 -*-
"""An env used as a social media."""
from typing import List, Any, Union, Generator, Tuple, Optional
from copy import deepcopy
import re
import random
import threading
import time
from loguru import logger
import concurrent.futures
import datetime
from datetime import timedelta

from agentscope.agents import AgentBase
from agentscope.message import Msg
from agentscope.exception import (
    EnvListenerError,
)
from agentscope.environment import (
    Env,
    BasicEnv,
    EventListener,
    Event,
    event_func,
)
from agentscope.models import ModelResponse
from agentscope.manager import ModelManager
from agentscope.studio._client import _studio_client
from agentscope.web.gradio.utils import user_input


SOCIAL_MEDIA_TEMPLATE = """
======= 朋友圈 开始 ========

## 最新动态:
{history}

======= 朋友圈 结束 ========
"""


class SocialMediaMember(BasicEnv):
    """A member of social media."""

    def __init__(
        self,
        name: str,
        agent: AgentBase,
        history_idx: int = 0,
    ) -> None:
        super().__init__(name)
        self._agent = agent
        self._history_idx = history_idx

    @property
    def agent_name(self) -> str:
        """Get the name of the agent."""
        return self._agent.name

    @property
    def history_idx(self) -> int:
        """Get the history index of the agent."""
        return self._history_idx

    @property
    def agent(self) -> AgentBase:
        """Get the agent of the member."""
        return self._agent

    def generate_post(self, recent_posts: List[Msg] = [], current_time: str = "") -> Msg:
        msg = self._agent(recent_posts, current_time)
        return msg


class SocialMedia(BasicEnv):
    """A social media env."""

    def __init__(
        self,
        name: str = None,
        model_config_name: str = None,
        announcement: Msg = None,
        participants: List[AgentBase] = None,
        all_history: bool = False,
        use_mention: bool = True,
        **kwargs: Any,
    ) -> None:
        """Init a SocialMedia instance.

        Args:
            name (`str`): The name of the social media.
            announcement (`Msg`): The announcement message.
            participants (`List[AgentBase]`): A list of agents
            all_history (`bool`): If `True`, new participant can see all
            history messages, else only messages generated after joining
            can be seen. Default to `False`.
            use_mention (`bool`): If `True`, the agent can mention other
            agents by @name. Default to `True`.
        """
        super().__init__(
            name=name,
            **kwargs,
        )
        self.children = {}
        for p in participants if participants else []:
            self.join(p)
        self.event_listeners = {}
        self.all_history = all_history
        if use_mention:
            self.add_listener(
                "speak",
                listener=Notifier(),
            )
        self.history = []
        self.announcement = announcement

    @event_func
    def join(self, agent: AgentBase) -> bool:
        """Add a participant to the social media."""
        if agent.name in self.children:
            return False
        self.children[agent.name] = SocialMediaMember(
            name=agent.name,
            agent=agent,
            history_idx=len(self.history),
        )
        self.add_listener("speak", Notifier())
        return True

    @event_func
    def leave(self, agent: AgentBase) -> bool:
        """Remove the participant agent from the social media."""
        if agent.agent_id not in self.children:
            return False
        del self.children[agent.agent_id]
        return True

    @event_func
    def speak(self, message: Msg) -> None:
        """Speak a message in the social media."""
        self.history.append(message)

    @event_func
    def get_history(self, agent_name: str) -> List[Msg]:
        """Get all history messages, since the participant join in the
        social media"""
        if agent_name not in self.children:
            # only participants can get history message
            return []
        if self.all_history:
            history_idx = 0
        else:
            history_idx = self.children[agent_name].history_idx
        return deepcopy(self.history[history_idx:])

    def describe(self, recent_posts: List[Msg] = []) -> str:
        """Get the description of the social media."""

        history = "\n\n".join(
            [
                f"{msg.name}({msg.content['timestamp']}): {msg.content['content']}"
                for msg in recent_posts
            ],
        )
        return SOCIAL_MEDIA_TEMPLATE.format(
            history=history,
        )

    @event_func
    def set_announcement(self, announcement: Msg) -> None:
        """Set the announcement of the social media."""
        self.announcement = announcement

    @event_func
    def get_announcement(self) -> Msg:
        """Get the announcement of the social media."""
        return deepcopy(self.announcement)

    # Syntaic sugar, not an event function
    def listen_to(
        self,
        target_names: List[str],
        listener: EventListener,
    ) -> None:
        """The listener will be called when a message whose name is in
        `target_names` is send to the social media."""
        if target_names is None or len(target_names) == 0:
            return

        class ListenTo(EventListener):
            """A middleware that activates `target_listener`"""

            def __init__(
                self,
                name: str,
                target_names: List[str],
                target_listener: EventListener,
            ) -> None:
                super().__init__(name=name)
                self.target_names = target_names
                self.target_listener = target_listener

            def __call__(self, env: Env, event: Event) -> None:
                if event.args["message"].name in self.target_names:
                    self.target_listener(env, event)

        if not self.add_listener(
            "speak",
            listener=ListenTo(
                name=f"listen_to_{listener.name}",
                target_names=target_names,
                target_listener=listener,
            ),
        ):
            raise EnvListenerError("Fail to add listener.")

    def generate_post(
        self,
        recent_posts: List[Msg] = [],
        current_time: str = "",
        **kwargs: Any,
    ) -> List[Msg]:
        """Let all agents to chat freely without any preset order"""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self.children[agent_name].post,
                    recent_posts=recent_posts,
                    current_time=current_time
                )
                for agent_name in self.children.keys()
            ]
            result = [future.result() for future in futures]
        return result

    def generate_post_in_sequence(
        self,
        agent_name_order: List[str] = None,
        recent_posts: List[Msg] = [],
        current_time: str = "",
    ) -> List[Msg]:
        """Let all agents generate posts in sequence
        Args:
            agent_name_order (`List[str]`): Order of speakers' names.
        """
        if agent_name_order is None:
            agent_name_order = [
                agent_name
                for agent_name in self.children.keys()
            ]
        result = []
        for agent_name in agent_name_order:
            result.append(self.children[agent_name].generate_post(recent_posts, current_time))
        return result


class Notifier(EventListener):
    """A listener that will call the mentioned agent"""

    def __init__(
        self,
    ) -> None:
        super().__init__(name="mentioned_notifier")
        self.pattern = re.compile(r"(?<=@)\w+")

    def __call__(self, media: Env, event: Event) -> None:
        names = self.pattern.findall(str(event.args["message"].content))
        names = list(set(names))

        for name in names:
            if name in media.children:
                logger.info(
                    f"{event.args['message'].name} mentioned {name}.",
                )
                media.children[name].agent.add_mentioned_message(
                    event.args["message"],
                )


class SocialMediaAgent(AgentBase):
    """
    An agent in a social media.
    """

    def __init__(  # pylint: disable=W0613
        self,
        # name: str = None,
        # sys_prompt: str = None,
        model_config_name: str = None,
        settings: dict = None,
        **kwargs: Any,
    ) -> None:
        name = settings.get("name", None)
        gender = settings.get("sex", None)
        sys_prompt = (
            f"""## 角色名称\n{name}\n\n"""
            f"""## 性别\n{gender}\n\n"""
            f"""## 角色介绍\n{settings.get('description', '')}\n\n"""
            f"""## 角色设定\n{settings.get('instructions', '')}\n\n"""
        )
        super().__init__(
            name=name,
            sys_prompt=sys_prompt,
            model_config_name=model_config_name,
        )
        self.media_history_length = 0
        self.media_slient_count = 0
        self.media = None
        self.mentioned_messages = []
        self.mentioned_messages_lock = threading.Lock()

    def add_mentioned_message(self, msg: Msg) -> None:
        """Add mentioned messages"""
        with self.mentioned_messages_lock:
            self.mentioned_messages.append(msg)

    def join(self, media: SocialMedia) -> bool:
        """Join a media"""
        self.media = media
        return media.join(self)

    def _is_mentioned(self) -> bool:
        """Check whether the agent is mentioned"""
        return bool(self.mentioned_messages)

    def _generate_mentioned_prompt(self) -> Tuple[bool, str]:
        """Generate a hint for the agent"""
        with self.mentioned_messages_lock:
            if len(self.mentioned_messages) > 0:
                hint = "You have been mentioned in the following messages:\n"
                hint += "\n".join(
                    [
                        f"{msg.name}: {msg.content}"
                        for msg in self.mentioned_messages
                    ],
                )
                return True, hint
            return False, ""

    def _want_to_speak(self, hint: str) -> bool:
        """Check whether the agent want to speak currently"""
        prompt = self.model.format(
            Msg(name="system", role="system", content=hint),
            Msg(
                name="user",
                role="user",
                content="基于以上的朋友圈内容，决定是否要发送一条新的朋友圈。"
                "如果不发送则返回 **否**，否则返回 **是**。",
            ),
        )
        response = self.model(
            prompt,
            max_retries=3,
        ).text
        logger.info(f"[SPEAK OR NOT] {self.name}: {response}")
        return "yes" in response.lower()

    def speak(
        self,
        content: Union[str, Msg, Generator[Tuple[bool, str], None, None]],
    ) -> None:
        """Speak to media.

        Args:
            content
            (`Union[str, Msg, Generator[Tuple[bool, str], None, None]]`):
                The content of the message to be spoken in social media.
        """
        super().speak(content)
        self.media.speak(content)

    def parse_func(self, response: ModelResponse) -> ModelResponse:
        lines = response.text.split('\n')
        in_content = False
        content = ''
        timestamp = None
        for line in lines:
            if in_content or line.startswith("内容："):
                in_content = True
                if line.startswith("内容："):
                    line = line[len("内容："):]
                if content:
                    content += '\n'
                content += line
            elif line.startswith("时间："):
                timestamp = line[len("时间："):]
        parsed = {
            'timestamp': timestamp.strip(),
            'content': content.strip(),
        }
        seconds = random.randint(0, 59)
        parsed['timestamp'] = parsed['timestamp'][:-2] + '%02d' % seconds
        logger.debug(f"response.text = {response.text} Parsed: {parsed}")
        return ModelResponse(text=response.text, parsed=parsed)

    def reply(self, recent_posts: List[Msg] = [], current_time: str = "") -> Msg:
        """Generate reply to chat media"""
        media_info = self.media.describe(recent_posts)
        reply_hint = ''
        mentioned, mentioned_hint = self._generate_mentioned_prompt()
        if mentioned:
            reply_hint = f'{mentioned_hint}\n{self.name}:'
        else:
            # decide whether to speak
            # if len(recent_posts) == 0 or self._want_to_speak(media_info):
                reply_hint = (
                    r"请给予以上的朋友圈内容，生成一条合适的朋友圈。"
                    r"生成要求如下：\n"
                    rf"1. 现在的时间是{current_time}，生成的朋友圈时间在未来一小时以内。\n"
                    r"2. 朋友圈内容需要符合人设，且符合当前朋友圈内容。\n"
                    r"3. 生成内容需要像日常聊天那样保持口语化、自然、流畅、简略，讲大白话。\n"
                    r"4. 回复禁止超过六十字，讨论请围绕主题，接地气，可以加入适当的语气词表达情感。\n"
                    r"5. 尽可能地避免使用特殊符号，例如：#、&、~等。\n"
                    r"6. 请按照下面的格式进行生成：\n"
                    r"时间：yyyy-MM-dd HH:mm:ss\n"
                    r"内容：(符合人设的朋友圈文本)\n"
                )
            # else:
            #     return Msg(name="assistant", role="assistant", content="")
        system_hint = (
            f"{self.sys_prompt}\n你正在浏览下面的朋友圈：\n"
            f"\n{media_info}\n{reply_hint}"
        )
        prompt = self.model.format(
            Msg(
                name="system",
                role="system",
                content=system_hint,
            )
        )
        prompt[-1]["content"] = prompt[-1]["content"].strip()
        logger.debug(prompt)
        response = self.model(
            prompt,
            parse_func=self.parse_func,
            max_retries=3,
        )
        msg = Msg(name=self.name, content=response.parsed, role="assistant")
        if response:
            self.speak(msg)
        return msg
