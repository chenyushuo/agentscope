# -*- coding: utf-8 -*-
"""A simple example of social media with three agents."""

import os
import argparse
import json

from envs.social_media import SocialMedia, SocialMediaAgent

import agentscope
from agentscope.message import Msg


def parse_args() -> argparse.Namespace:
    """Parse arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--logger-level",
        choices=["DEBUG", "INFO"],
        default="INFO",
    )
    parser.add_argument(
        "--use-dist",
        action="store_true",
    )
    parser.add_argument(
        "--studio-url",
        default=None,
        type=str,
    )
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    """Example for social media"""
    # Prepare the model configuration
    YOUR_MODEL_CONFIGURATION_NAME = "vllm"
    YOUR_MODEL_CONFIGURATION = [
        {
            "model_type": "openai_chat",
            "config_name": "vllm",
            "model_name": "/mnt/data/shared/checkpoints/qwen/qwen2.5/Qwen2.5-7B-Instruct",
            "api_key": "None",
            "client_args": {
                "base_url": "http://127.0.0.1:8000/v1/"
            },
            "generate_args": {
                "temperature": 0.8,
                "max_tokens": 300,
            }
        },
    ]

    # Initialize the agents
    agentscope.init(
        model_configs=YOUR_MODEL_CONFIGURATION,
        use_monitor=False,
        logger_level=args.logger_level,
        studio_url=args.studio_url,
    )

    ann = Msg(  # announcement暂时没有在prompt中使用
        name="管理员",
        content=(
            "【温馨提醒】亲爱的社区成员们，为了维护我们共同的交流空间，请大家在发布内容时遵守社区规定，保持友善交流，共建和谐环境。感谢大家的理解与支持！"
        ),
        role="system",
    )
    r = SocialMedia(name="chat", announcement=ann, model_config_name=YOUR_MODEL_CONFIGURATION_NAME, to_dist=args.use_dist)

    members = []
    with open('chatroom/personality.json', 'r') as f:
        for line in f.readlines():
            persona = json.loads(line)
            member = SocialMediaAgent(
                settings=persona,
                model_config_name=YOUR_MODEL_CONFIGURATION_NAME,
                to_dist=args.use_dist
            )
            member.join(r)
            members.append(member)
    recent_posts = []
    with open('chatroom/history.txt', 'r') as f:
        for line in f.readlines():
            name, content = line.split(': ', 1)
            content = eval(content)
            recent_posts.append(Msg(name=name, content=content, role="assistant"))

    # Start
    result = r.generate_post(
        recent_posts = [],
        current_time="2024-10-15 15:00:00",
    )
    print(result)


if __name__ == "__main__":
    main(parse_args())
