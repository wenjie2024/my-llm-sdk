from my_llm_sdk.client import LLMClient
import argparse
import asyncio
import sys
import shutil
import os

def copy_template(src_name, dest_name, description):
    """Copy template file to destination if it doesn't exist."""
    if os.path.exists(dest_name):
        print(f"⚠️  {description} already exists at {dest_name}. Skipping.")
    else:
        # Assuming templates are in the package or just hardcoding simple defaults here for now
        # Ideally, we ship templates in the package data.
        # For this demo, let's write default content directly.
        
        content = ""
        if "project" in dest_name:
            content = """project_name: my-awesome-project
routing_policies:
  - name: default-priority
    strategy: priority
    params:
      priority_list: gemini-2.5-flash,qwen-max
model_registry:
  gemini-2.5-flash:
    provider: google
    model_id: gemini-2.5-flash
    rpm: 1000
    tpm: 1000000
  qwen-max:
    provider: dashscope
    model_id: qwen-max
    rpm: 600
    tpm: 100000
allowed_regions: ["us", "cn", "sg"]
allow_logging: true
budget_strict_mode: true
"""
        elif "config" in dest_name:
            content = """api_keys:
  google: "YOUR_GEMINI_API_KEY"
  dashscope: "YOUR_DASHSCOPE_API_KEY"
  openai: "YOUR_OPENAI_API_KEY"

daily_spend_limit: 1.0

personal_model_overrides: {}

personal_routing_policies: []

endpoints: []
"""
        
        with open(dest_name, "w") as f:
            f.write(content)
        print(f"✅ Created {description} at {dest_name}")

def update_gitignore(entry: str):
    """Ensure entry exists in .gitignore."""
    gitignore_path = ".gitignore"
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        
        if entry not in content:
            # Append if not present
            with open(gitignore_path, "a") as f:
                # Ensure newline before append if file not empty and doesn't end with newline
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write(f"{entry}\n")
            print(f"🔒 Added '{entry}' to existing .gitignore")
        else:
            print(f"🔒 '{entry}' already in .gitignore")
    else:
        # Create new
        with open(gitignore_path, "w") as f:
            f.write(f"{entry}\n")
        print(f"🔒 Created .gitignore with '{entry}'")

def main():
    parser = argparse.ArgumentParser(description="LLM SDK CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Doctor Command
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    
    # Generate Command
    gen_parser = subparsers.add_parser("generate", help="Generate text")
    gen_parser.add_argument("--prompt", help="Prompt for generation", default="Hello Vibe")
    gen_parser.add_argument("--model", help="Model alias", default="gpt-4")
    
    # Init Command
    init_parser = subparsers.add_parser("init", help="Initialize configuration files")
    
    # Global Args
    parser.add_argument("--project-config", help="Path to project config", default="llm.project.yaml")
    parser.add_argument("--user-config", help="Path to user config", default="config.yaml")

    args = parser.parse_args()
    
    if args.command == "init":
        print("🚀 Initializing SDK Configuration...")
        copy_template("template.project.yaml", "llm.project.yaml", "Project Config")
        copy_template("template.user.yaml", "config.yaml", "User Config (Secrets)")
        
        # Security: Add to gitignore
        update_gitignore("config.yaml")
        
        print("\n🎉 Done! Please edit 'config.yaml' to add your API Keys.")
        return

    # Initialize Client for other commands
    try:
        client = LLMClient(project_config_path=args.project_config, user_config_path=args.user_config)
    except Exception as e:
        if args.command in ["doctor", "generate"]:
            print(f"❌ Config Error: {e}")
            print("Tip: Run 'python -m my_llm_sdk.cli init' to create config files, or check paths.")
            sys.exit(1)
        raise e

    if args.command == "doctor":
        asyncio.run(client.run_doctor())
    elif args.command == "generate":
        try:
            res = client.generate(args.prompt, args.model)
            print(res)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
