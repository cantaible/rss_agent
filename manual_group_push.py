import argparse

from group_push_service import force_push_groups_once


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manually trigger one forced group push run."
    )
    parser.add_argument(
        "--chat-id",
        action="append",
        dest="chat_ids",
        help="Only push to the specified chat_id. Can be passed multiple times.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    target_chat_ids = args.chat_ids or None

    if target_chat_ids:
        print(f"🚀 Force pushing groups once for chat_ids={target_chat_ids}")
    else:
        print("🚀 Force pushing groups once for all enabled groups")

    force_push_groups_once(target_chat_ids=target_chat_ids)
    print("✅ Force group push completed.")
