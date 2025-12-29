import sys
import asyncio
import argparse
from src.client import LLMClient

def main():
    parser = argparse.ArgumentParser(description="LLM SDK CLI")
    parser.add_argument("command", choices=["doctor", "generate"], help="Command to run")
    parser.add_argument("--prompt", help="Prompt for generation", default="Hello Vibe")
    parser.add_argument("--model", help="Model alias", default="gpt-4")
    parser.add_argument("--project-config", help="Path to project config", default="llm.project.yaml")
    parser.add_argument("--user-config", help="Path to user config", default="config.yaml")
    
    args = parser.parse_args()
    
    client = LLMClient(project_config_path=args.project_config, user_config_path=args.user_config)
    
    if args.command == "doctor":
        asyncio.run(client.run_doctor())
    elif args.command == "generate":
        try:
            res = client.generate(args.prompt, args.model)
            print(res)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
