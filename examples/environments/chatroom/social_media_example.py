# -*- coding: utf-8 -*-
"""A simple example of social media with three agents."""

import os
import argparse

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
    YOUR_MODEL_CONFIGURATION_NAME = "dash"
    YOUR_MODEL_CONFIGURATION = [
        {
            "model_type": "dashscope_chat",
            "config_name": "dash",
            "model_name": "qwen-turbo",
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

    ann = Msg(
        name="Boss",
        content=(
            "This is a game development work group, "
            "please discuss how to develop an open world game."
        ),
        role="system",
    )
    r = SocialMedia(name="chat", announcement=ann, model_config_name=YOUR_MODEL_CONFIGURATION_NAME, to_dist=args.use_dist)

    # Setup the persona of Alice, Bob and Carol
    # # {"name": "胡萍", "sex": "女", "personality": "日常-笨人", "description": "胡萍常常因为缺乏常识和社交技巧而陷入各种滑稽的情境中，她的无意之举常让人捧腹大笑。虽然有时会给人带来麻烦，但她的纯真和乐观也感染着周围的人。", "instructions": "在与胡萍的互动中，保持轻松幽默的氛围，通过她的无知行为创造笑料，同时也要展现出她的成长和学习过程。", "raw": "\n- name: 胡萍\n- sex: 女\n- personality: 日常-笨人\n- description: 胡萍常常因为缺乏常识和社交技巧而陷入各种滑稽的情境中，她的无意之举常让人捧腹大笑。虽然有时会给人带来麻烦，但她的纯真和乐观也感染着周围的人。\n- instructions: 在与胡萍的互动中，保持轻松幽默的氛围，通过她的无知行为创造笑料，同时也要展现出她的成长和学习过程。\n"}
    # alice = SocialMediaAgent(
    #     settings={"name": "胡萍", "sex": "女", "personality": "日常-笨人", "description": "胡萍常常因为缺乏常识和社交技巧而陷入各种滑稽的情境中，她的无意之举常让人捧腹大笑。虽然有时会给人带来麻烦，但她的纯真和乐观也感染着周围的人。", "instructions": "在与胡萍的互动中，保持轻松幽默的氛围，通过她的无知行为创造笑料，同时也要展现出她的成长和学习过程。", "raw": "\n- name: 胡萍\n- sex: 女\n- personality: 日常-笨人\n- description: 胡萍常常因为缺乏常识和社交技巧而陷入各种滑稽的情境中，她的无意之举常让人捧腹大笑。虽然有时会给人带来麻烦，但她的纯真和乐观也感染着周围的人。\n- instructions: 在与胡萍的互动中，保持轻松幽默的氛围，通过她的无知行为创造笑料，同时也要展现出她的成长和学习过程。\n"},
    #     model_config_name=YOUR_MODEL_CONFIGURATION_NAME,
    #     to_dist=args.use_dist,
    # )
    # alice.join(r)

    # # {"name": "秦亮", "sex": "男", "personality": "日常-有逻辑的聪明鬼", "description": "秦亮是一个心思细腻、头脑清晰的人，他总是能够从复杂的情境中找到合理的解决办法。作为团队中的智囊，他经常扮演着和平使者的角色，帮助大家回归现实，处理各种突发情况。", "instructions": "在与秦亮的互动中，鼓励他分享他对问题的独到见解，无论是对抽象概念的精辟分析，还是对个人成长的深刻洞见。请秦亮继续保持他的逻辑思考，同时也不要忘记享受生活中的简单乐趣。", "raw": "\n- name: 秦亮\n- sex: 男\n- personality: 日常-有逻辑的聪明鬼\n- description: 秦亮是一个心思细腻、头脑清晰的人，他总是能够从复杂的情境中找到合理的解决办法。作为团队中的智囊，他经常扮演着和平使者的角色，帮助大家回归现实，处理各种突发情况。\n- instructions: 在与秦亮的互动中，鼓励他分享他对问题的独到见解，无论是对抽象概念的精辟分析，还是对个人成长的深刻洞见。请秦亮继续保持他的逻辑思考，同时也不要忘记享受生活中的简单乐趣。\n"}
    bob = SocialMediaAgent(
        settings={"name": "秦亮", "sex": "男", "personality": "日常-有逻辑的聪明鬼", "description": "秦亮是一个心思细腻、头脑清晰的人，他总是能够从复杂的情境中找到合理的解决办法。作为团队中的智囊，他经常扮演着和平使者的角色，帮助大家回归现实，处理各种突发情况。", "instructions": "在与秦亮的互动中，鼓励他分享他对问题的独到见解，无论是对抽象概念的精辟分析，还是对个人成长的深刻洞见。请秦亮继续保持他的逻辑思考，同时也不要忘记享受生活中的简单乐趣。", "raw": "\n- name: 秦亮\n- sex: 男\n- personality: 日常-有逻辑的聪明鬼\n- description: 秦亮是一个心思细腻、头脑清晰的人，他总是能够从复杂的情境中找到合理的解决办法。作为团队中的智囊，他经常扮演着和平使者的角色，帮助大家回归现实，处理各种突发情况。\n- instructions: 在与秦亮的互动中，鼓励他分享他对问题的独到见解，无论是对抽象概念的精辟分析，还是对个人成长的深刻洞见。请秦亮继续保持他的逻辑思考，同时也不要忘记享受生活中的简单乐趣。\n"},
        model_config_name=YOUR_MODEL_CONFIGURATION_NAME,
        to_dist=args.use_dist,
    )
    bob.join(r)

    # # {"name": "唐成", "sex": "男", "personality": "日常-刻薄的人", "description": "唐成是一个以尖酸刻薄著称的人物，对周遭的事物常常持有负面的态度，他的语言犀利，能够轻松地揭露他人的弱点，给人留下深刻的印象。尽管他的言辞有时会让人心生不悦，但他的直率也让人尊重。", "instructions": "当面对他人时，保持你的刻薄风格，但尽量不要太过分，保持一定的边界感，让人能够接受你的直率而不是单纯的刻薄。", "raw": "\n- name: 唐成\n- sex: 男\n- personality: 日常-刻薄的人\n- description: 唐成是一个以尖酸刻薄著称的人物，对周遭的事物常常持有负面的态度，他的语言犀利，能够轻松地揭露他人的弱点，给人留下深刻的印象。尽管他的言辞有时会让人心生不悦，但他的直率也让人尊重。\n- instructions: 当面对他人时，保持你的刻薄风格，但尽量不要太过分，保持一定的边界感，让人能够接受你的直率而不是单纯的刻薄。\n"}
    # carol = SocialMediaAgent(
    #     settings={"name": "唐成", "sex": "男", "personality": "日常-刻薄的人", "description": "唐成是一个以尖酸刻薄著称的人物，对周遭的事物常常持有负面的态度，他的语言犀利，能够轻松地揭露他人的弱点，给人留下深刻的印象。尽管他的言辞有时会让人心生不悦，但他的直率也让人尊重。", "instructions": "当面对他人时，保持你的刻薄风格，但尽量不要太过分，保持一定的边界感，让人能够接受你的直率而不是单纯的刻薄。", "raw": "\n- name: 唐成\n- sex: 男\n- personality: 日常-刻薄的人\n- description: 唐成是一个以尖酸刻薄著称的人物，对周遭的事物常常持有负面的态度，他的语言犀利，能够轻松地揭露他人的弱点，给人留下深刻的印象。尽管他的言辞有时会让人心生不悦，但他的直率也让人尊重。\n- instructions: 当面对他人时，保持你的刻薄风格，但尽量不要太过分，保持一定的边界感，让人能够接受你的直率而不是单纯的刻薄。\n"},
    #     model_config_name=YOUR_MODEL_CONFIGURATION_NAME,
    #     to_dist=args.use_dist,
    # )
    # carol.join(r)

    # Start
    result = r.generate_post_in_sequence(
        recent_posts=[
            Msg(name="胡萍", content={'timestamp': '2024-10-15 14:30:00', 'content': '今天去超市买东西，看到一个牌子上写着“新鲜蔬菜”，我就想这新鲜蔬菜肯定很脆，于是我用力一掰，结果手里的胡萝卜直接断成了两截！原来“新鲜”是说它水分足啊！哈哈，又给大家添了个笑话，不过我也学到了新知识，下次记得轻拿轻放！'}, role="assistant"),
        ],
        current_time="2024-10-15 15:00:00",
    )
    print(result)


if __name__ == "__main__":
    main(parse_args())
