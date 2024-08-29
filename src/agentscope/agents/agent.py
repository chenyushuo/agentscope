# -*- coding: utf-8 -*-
""" Base class for Agent """

from __future__ import annotations
from types import GeneratorType
from typing import Optional, Generator, Tuple
from typing import Sequence
from typing import Union
from typing import Any
from typing import Type
import json
import uuid
from loguru import logger

from agentscope.agents.operator import Operator
from agentscope.rpc.rpc_config import DistConf
from agentscope.rpc.rpc_async import async_func
from agentscope.rpc.rpc_meta import RpcMeta
from agentscope.logging import log_stream_msg, log_msg
from agentscope.manager import ModelManager
from agentscope.message import Msg
from agentscope.memory import TemporaryMemory


class AgentBase(Operator, metaclass=RpcMeta):
    """Base class for all agents.

    All agents should inherit from this class and implement the `reply`
    function.
    """

    _version: int = 1

    def __init__(
        self,
        name: str,
        sys_prompt: Optional[str] = None,
        model_config_name: str = None,
        use_memory: bool = True,
        to_dist: Optional[Union[DistConf, bool]] = False,
    ) -> None:
        r"""Initialize an agent from the given arguments.

        Args:
            name (`str`):
                The name of the agent.
            sys_prompt (`Optional[str]`):
                The system prompt of the agent, which can be passed by args
                or hard-coded in the agent.
            model_config_name (`str`, defaults to None):
                The name of the model config, which is used to load model from
                configuration.
            use_memory (`bool`, defaults to `True`):
                Whether the agent has memory.
            to_dist (`Optional[Union[DistConf, bool]]`, default to `False`):
                The configurations passed to :py:meth:`to_dist` method. Used in
                :py:class:`_AgentMeta`, when this parameter is provided,
                the agent will automatically be converted into its distributed
                version. Below are some examples:

                .. code-block:: python

                    # run as a sub process
                    agent = XXXAgent(
                        # ... other parameters
                        to_dist=True,
                    )

                    # connect to an existing agent server
                    agent = XXXAgent(
                        # ... other parameters
                        to_dist=DistConf(
                            host="<ip of your server>",
                            port=<port of your server>,
                            # other parameters
                        ),
                    )

                See :doc:`Tutorial<tutorial/208-distribute>` for detail.
        """
        self.name = name
        self.sys_prompt = sys_prompt

        # TODO: support to receive a ModelWrapper instance
        if model_config_name is not None:
            model_manager = ModelManager.get_instance()
            self.model = model_manager.get_model_by_config_name(
                model_config_name,
            )

        if use_memory:
            self.memory = TemporaryMemory()
        else:
            self.memory = None

        # The audience of this agent, which means if this agent generates a
        # response, it will be passed to all agents in the audience.
        self._audience = None
        # convert to distributed agent, conversion is in `_AgentMeta`
        if to_dist is not False and to_dist is not None:
            logger.info(
                f"Convert {self.__class__.__name__}[{self.name}] into"
                " a distributed agent.",
            )

    @classmethod
    def generate_agent_id(cls) -> str:
        """Generate the agent_id of this agent instance"""
        # TODO: change cls.__name__ into a global unique agent_type
        return uuid.uuid4().hex

    # todo: add a unique agent_type field to distinguish different agent class
    @classmethod
    def get_agent_class(cls, agent_class_name: str) -> Type[AgentBase]:
        """Get the agent class based on the specific agent class name.

        Args:
            agent_class_name (`str`): the name of the agent class.

        Raises:
            ValueError: Agent class name not exits.

        Returns:
            Type[AgentBase]: the AgentBase subclass.
        """
        if agent_class_name not in cls._registry:
            raise ValueError(f"Agent class <{agent_class_name}> not found.")
        return cls._registry[agent_class_name]  # type: ignore[return-value]

    @classmethod
    def register_agent_class(cls, agent_class: Type[AgentBase]) -> None:
        """Register the agent class into the registry.

        Args:
            agent_class (Type[AgentBase]): the agent class to be registered.
        """
        agent_class_name = agent_class.__name__
        if agent_class_name in cls._registry:
            logger.info(
                f"Agent class with name [{agent_class_name}] already exists.",
            )
        else:
            cls._registry[agent_class_name] = agent_class

    @async_func
    def reply(self, x: Optional[Union[Msg, Sequence[Msg]]] = None) -> Msg:
        """Define the actions taken by this agent.

        Args:
            x (`Optional[Union[Msg, Sequence[Msg]]]`, defaults to `None`):
                The input message(s) to the agent, which also can be omitted if
                the agent doesn't need any input.

        Returns:
            `Msg`: The output message generated by the agent.

        Note:
            Given that some agents are in an adversarial environment,
            their input doesn't include the thoughts of other agents.
        """
        raise NotImplementedError(
            f"Agent [{type(self).__name__}] is missing the required "
            f'"reply" function.',
        )

    @async_func
    def __call__(self, *args: Any, **kwargs: Any) -> Msg:
        """Calling the reply function, and broadcast the generated
        response to all audiences if needed."""
        res = self.reply(*args, **kwargs)

        # broadcast to audiences if needed
        if self._audience is not None:
            self._broadcast_to_audience(res)

        return res

    def speak(
        self,
        content: Union[str, Msg, Generator[Tuple[bool, str], None, None]],
    ) -> None:
        """
        Speak out the message generated by the agent. If a string is given,
        a Msg object will be created with the string as the content.

        Args:
            content
            (`Union[str, Msg, Generator[Tuple[bool, str], None, None]`):
                The content of the message to be spoken out. If a string is
                given, a Msg object will be created with the agent's name, role
                as "assistant", and the given string as the content.
                If the content is a Generator, the agent will speak out the
                message chunk by chunk.
        """
        if isinstance(content, str):
            log_msg(
                Msg(
                    name=self.name,
                    content=content,
                    role="assistant",
                ),
            )
        elif isinstance(content, Msg):
            log_msg(content)
        elif isinstance(content, GeneratorType):
            # The streaming message must share the same id for displaying in
            # the agentscope studio.
            msg = Msg(name=self.name, content="", role="assistant")
            for last, text_chunk in content:
                msg.content = text_chunk
                log_stream_msg(msg, last=last)
        else:
            raise TypeError(
                "From version 0.0.5, the speak method only accepts str or Msg "
                f"object, got {type(content)} instead.",
            )

    def observe(self, x: Union[Msg, Sequence[Msg]]) -> None:
        """Observe the input, store it in memory without response to it.

        Args:
            x (`Union[Msg, Sequence[Msg]]`):
                The input message to be recorded in memory.
        """
        if self.memory:
            self.memory.add(x)

    def reset_audience(self, audience: Sequence[AgentBase]) -> None:
        """Set the audience of this agent, which means if this agent
        generates a response, it will be passed to all audiences.

        Args:
            audience (`Sequence[AgentBase]`):
                The audience of this agent, which will be notified when this
                agent generates a response message.
        """
        # TODO: we leave the consideration of nested msghub for future.
        #  for now we suppose one agent can only be in one msghub
        self._audience = [_ for _ in audience if _ != self]

    def clear_audience(self) -> None:
        """Remove the audience of this agent."""
        # TODO: we leave the consideration of nested msghub for future.
        #  for now we suppose one agent can only be in one msghub
        self._audience = None

    def rm_audience(
        self,
        audience: Union[Sequence[AgentBase], AgentBase],
    ) -> None:
        """Remove the given audience from the Sequence"""
        if not isinstance(audience, Sequence):
            audience = [audience]

        for agent in audience:
            if self._audience is not None and agent in self._audience:
                self._audience.pop(self._audience.index(agent))
            else:
                logger.warning(
                    f"Skip removing agent [{agent.name}] from the "
                    f"audience for its inexistence.",
                )

    def _broadcast_to_audience(self, x: dict) -> None:
        """Broadcast the input to all audiences."""
        for agent in self._audience:
            agent.observe(x)

    def __str__(self) -> str:
        serialized_fields = {
            "name": self.name,
            "type": self.__class__.__name__,
            "sys_prompt": self.sys_prompt,
            "agent_id": self.agent_id,
        }
        if hasattr(self, "model"):
            serialized_fields["model"] = {
                "model_type": self.model.model_type,
                "config_name": self.model.config_name,
            }
        return json.dumps(serialized_fields, ensure_ascii=False)

    @property
    def agent_id(self) -> str:
        """The unique id of this agent.

        Returns:
            str: agent_id
        """
        return self._oid

    @agent_id.setter
    def agent_id(self, agent_id: str) -> None:
        """Set the unique id of this agent."""
        self._oid = agent_id
