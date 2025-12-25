"""
Chat commands for Comani.
"""

import argparse


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register chat commands."""
    chat_parser = subparsers.add_parser("chat", help="Chat with Grok AI")
    chat_parser.add_argument("prompt", nargs="?", help="Prompt to send (omit for interactive mode)")
    chat_parser.add_argument("-s", "--system", help="System prompt")
    chat_parser.add_argument("-m", "--model", default="grok-3-fast", help="Model to use (default: grok-3-fast)")
    chat_parser.add_argument("--no-thinking", action="store_true", help="Hide thinking/reasoning output")
    chat_parser.set_defaults(func=cmd_chat)


def cmd_chat(args: argparse.Namespace) -> int:
    """Chat with Grok AI using grok-api."""
    from grok_api.core import Grok

    try:
        client = Grok(model=args.model)
    except Exception as e:
        print(f"Error initializing Grok: {e}")
        return 1

    extra_data = None

    # Handle initial prompt
    if args.prompt:
        prompt = args.prompt
        if args.system:
            prompt = f"System: {args.system}\n\nUser: {prompt}"

        print("🤖 Grok: ", end="", flush=True)
        try:
            for chunk in client.chat_stream(prompt):
                if chunk.get("error"):
                    print(f"\nError: {chunk['error']}")
                    return 1
                if chunk.get("token"):
                    print(chunk["token"], end="", flush=True)
            print() # Newline after response
            return 0
        except Exception as e:
            print(f"\nError during chat: {e}")
            return 1

    # Interactive mode
    print("🤖 Grok Chat (type 'exit' to quit)")
    print("=" * 40)

    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            if not user_input:
                continue

            prompt = user_input
            if extra_data is None and args.system:
                prompt = f"System: {args.system}\n\nUser: {user_input}"

            print("🤖 Grok: ", end="", flush=True)

            last_meta = None
            for chunk in client.chat_stream(prompt, extra_data=extra_data):
                if chunk.get("error"):
                    print(f"\nError: {chunk['error']}")
                    break
                if chunk.get("token"):
                    print(chunk["token"], end="", flush=True)
                if chunk.get("meta"):
                    last_meta = chunk["meta"]

            print() # Newline after response
            if last_meta:
                extra_data = last_meta.get("extra_data")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

    return 0
