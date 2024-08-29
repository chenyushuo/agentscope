# -*- coding: utf-8 -*-
"""A proxy object which represent a object located in a rpc server."""
from typing import Any, Callable
from functools import partial
from abc import ABC
from inspect import getmembers, isfunction
from types import FunctionType

try:
    import cloudpickle as pickle
except ImportError as e:
    from agentscope.utils.common import ImportErrorReporter

    pickle = ImportErrorReporter(e, "distribute")

from ..rpc import RpcAgentClient, call_func_in_thread
from ..exception import AgentServerUnsupportedMethodError, AgentCreationError
from ..studio._client import _studio_client
from ..server import RpcAgentServerLauncher


def get_public_methods(cls: type) -> list[str]:
    """Get all public methods of the given class."""
    return [
        name
        for name, member in getmembers(cls, predicate=isfunction)
        if isinstance(member, FunctionType) and not name.startswith("_")
    ]


class RpcObject(ABC):
    """A proxy object which represent an object located in a rpc server."""

    def __init__(
        self,
        cls: type,
        oid: str,
        host: str,
        port: int,
        max_pool_size: int = 8192,
        max_timeout_seconds: int = 7200,
        local_mode: bool = True,
        connect_existing: bool = False,
        configs: dict = None,
    ) -> None:
        """Initialize the rpc object.

        Args:
            cls (`type`): The class of the object in the rpc server.
            oid (`str`): The id of the object in the rpc server.
            host (`str`): The host of the rpc server.
            port (`int`): The port of the rpc server.
            max_pool_size (`int`, defaults to `8192`):
                Max number of task results that the server can accommodate.
            max_timeout_seconds (`int`, defaults to `7200`):
                Timeout for task results.
            local_mode (`bool`, defaults to `True`):
                Whether the started gRPC server only listens to local
                requests.
            connect_existing (`bool`, defaults to `False`):
                Set to `True`, if the object is already running on the
                server.
        """
        self.host = host
        self.port = port
        self._agent_id = oid
        self._cls = cls
        self._supported_attributes = get_public_methods(cls)
        self.connect_existing = connect_existing

        if self.port is None and _studio_client.active:
            server = _studio_client.alloc_server()
            if "host" in server:
                if RpcAgentClient(
                    host=server["host"],
                    port=server["port"],
                ).is_alive():
                    self.host = server["host"]
                    self.port = server["port"]
        launch_server = self.port is None
        self.server_launcher = None
        if launch_server:
            # check studio first
            self.host = "localhost"
            studio_url = None
            if _studio_client.active:
                studio_url = _studio_client.studio_url
            self.server_launcher = RpcAgentServerLauncher(
                host=self.host,
                port=self.port,
                max_pool_size=max_pool_size,
                max_timeout_seconds=max_timeout_seconds,
                local_mode=local_mode,
                custom_agent_classes=[cls],
                studio_url=studio_url,  # type: ignore[arg-type]
            )
            self._launch_server()
        self.client = RpcAgentClient(self.host, self.port)
        if not connect_existing:
            self.create(configs)
        else:
            self._creating_stub = None

    def create(self, configs: dict) -> None:
        """create the object on the rpc server."""
        self._creating_stub = call_func_in_thread(
            partial(
                self.client.create_agent,
                configs,
                self._agent_id,
            ),
        )

    def _launch_server(self) -> None:
        """Launch a rpc server and update the port and the client"""
        self.server_launcher.launch()
        self.port = self.server_launcher.port
        self.client = RpcAgentClient(
            host=self.host,
            port=self.port,
        )

    def stop(self) -> None:
        """Stop the RpcAgent and the rpc server."""
        if self.server_launcher is not None:
            self.server_launcher.shutdown()

    def _check_created(self) -> None:
        """Check if the object is created on the rpc server."""
        if self._creating_stub is not None:
            response = self._creating_stub.result()
            if response is not True:
                if issubclass(response.__class__, Exception):
                    raise response
                raise AgentCreationError(self.host, self.port)
            self._creating_stub = None

    def _call_rpc_func(self, func_name: str, args: dict) -> Any:
        """Call a function in rpc server."""
        self._check_created()
        return pickle.loads(
            self.client.call_agent_func(
                agent_id=self._agent_id,
                func_name=func_name,
                value=pickle.dumps(args),
            ),
        )

    def __getattr__(self, name: str) -> Callable:
        if name not in self._supported_attributes:
            raise AttributeError from AgentServerUnsupportedMethodError(
                host=self.host,
                port=self.port,
                oid=self._agent_id,
                func_name=name,
            )

        def wrapper(*args, **kwargs) -> Any:  # type: ignore[no-untyped-def]
            return self._call_rpc_func(
                func_name=name,
                args={"args": args, "kwargs": kwargs},
            )

        return wrapper

    def __getstate__(self) -> dict:
        """For serialization."""
        state = self.__dict__.copy()
        del state["server_launcher"]
        return state

    def __setstate__(self, state: dict) -> None:
        """For deserialization."""
        self.__dict__.update(state)
        self.server_launcher = None

    def __del__(self) -> None:
        self.stop()

    def __deepcopy__(self, memo: dict) -> Any:
        """For deepcopy."""
        if id(self) in memo:
            return memo[id(self)]

        clone = RpcObject(
            cls=self._cls,
            oid=self._agent_id,
            host=self.host,
            port=self.port,
            connect_existing=True,
        )
        memo[id(self)] = clone

        return clone