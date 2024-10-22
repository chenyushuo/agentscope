# -*- coding: utf-8 -*-
"""A simple example of social media with three agents."""

import os
import argparse
import json
import numpy as np
import pandas as pd

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
    YOUR_MODEL_CONFIGURATION_NAME = "dash"
    YOUR_MODEL_CONFIGURATION = [
        {
            "model_type": "dashscope_chat",
            "config_name": "dash",
            "model_name": "qwen-max",
            "api_key": os.environ.get("DASH_API_KEY", ""),
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
    name2persona = {}
    with open('chatroom/sub_persona.json', 'r') as f:
        for line in f.readlines():
            persona = json.loads(line)
            name2persona[persona['name']] = persona
            member = SocialMediaAgent(
                settings=persona,
                model_config_name=YOUR_MODEL_CONFIGURATION_NAME,
                to_dist=args.use_dist
            )
            member.join(r)
            members.append(member)
    recent_posts = []
    # with open('chatroom/history.txt', 'r') as f:
    #     for line in f.readlines():
    #         name, content = line.split(': ', 1)
    #         content = eval(content)
    #         recent_posts.append(Msg(name=name, content=content, role="assistant"))

    # Start
    # result = r.generate_post(
    #     recent_posts = [],
    #     current_time="2024-10-15 15:00:00",
    # )
    # print(result)
    recent_news = []
    with open('chatroom/news.txt', 'r') as f:
        for line in f.readlines():
            recent_news.append(line.strip())
    time_list = [
        "2024-10-15 8:00:00",
        "2024-10-15 11:00:00",
        "2024-10-15 14:00:00",
        "2024-10-15 16:00:00",
        "2024-10-15 19:00:00",
        "2024-10-15 21:00:00",
    ]
    result_dict = {}
    news_num = len(recent_news) // len(time_list)
    for i, current_time in enumerate(time_list):
        news = list(np.random.choice(recent_news[i * news_num: (i + 1) * news_num], np.ceil(news_num / 2), replace=False))
        result = r.generate_post_in_sequence(
            recent_posts=recent_posts,
            recent_news=news, # recent_news[i * news_num: (i + 1) * news_num],
            current_time=current_time,
        )
        # print(result)
        result_dict[current_time] = result
        recent_posts = list(np.random.choice(result, 8, replace=False))
    result_df = pd.DataFrame(columns=['时间', '角色类型', '姓名', '性别', '个人描述', '朋友圈内容'])
    for current_time, result in result_dict.items():
        for msg in result:
            persona = name2persona[msg.name]
            result_df = result_df._append({
                '时间': current_time,
                '角色类型': persona['personality'],
                '姓名': msg.name,
                '性别': persona['sex'],
                '个人描述': persona['description'],
                '朋友圈内容': msg.content['content']
            }, ignore_index=True)
    print(result_df)
    result_df.to_csv('chatroom/result.csv', index=False)


if __name__ == "__main__":
    main(parse_args())
