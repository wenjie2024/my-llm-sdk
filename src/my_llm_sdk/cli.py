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
    
    # Budget Command (V0.5.0)
    budget_parser = subparsers.add_parser("budget", help="Budget & Reporting")
    budget_subparsers = budget_parser.add_subparsers(dest="budget_command", help="Budget actions")
    
    # budget status (today)
    status_parser = budget_subparsers.add_parser("status", help="Show today's spend & status")
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # budget report
    report_parser = budget_subparsers.add_parser("report", help="Show cost trend")
    report_parser.add_argument("--days", type=int, default=7, help="Number of days")
    
    # budget top
    top_parser = budget_subparsers.add_parser("top", help="Show top consumers")
    top_parser.add_argument("--by", choices=["provider", "model"], default="model", help="Dimension to group by")
    top_parser.add_argument("--days", type=int, default=7, help="Number of days")

    # Init Command
    init_parser = subparsers.add_parser("init", help="Initialize configuration files")
    
    # Global Args
    parser.add_argument("--project-config", help="Path to project config", default="llm.project.yaml")
    parser.add_argument("--user-config", help="Path to user config", default="config.yaml")

    args = parser.parse_args()
    
    if args.command == "init":
        print("🚀 Initializing SDK Configuration...")
        
        # 1. Main Project Config (Minimal)
        project_content = """project_name: my-awesome-project
routing_policies:
  - name: default-priority
    strategy: priority
    params:
      priority_list: gemini-2.5-flash,qwen-max

# Project-level settings
settings:
  optimize_images: true

allowed_regions: ["us", "cn", "sg"]
allow_logging: true
budget_strict_mode: true

model_registry:
  # This section is now mainly managed in llm.project.d/*.yaml
  # Global defaults can go here.
  default:
    name: default
    provider: google
    model_id: gemini-2.5-flash
    pricing:
      input_per_1m_tokens: 0.075
      output_per_1m_tokens: 0.30
"""
        with open("llm.project.yaml", "w", encoding='utf-8') as f:
            f.write(project_content)
        print("✅ Created llm.project.yaml")

        # 2. Modular Configs (llm.project.d/)
        os.makedirs("llm.project.d", exist_ok=True)
        
        # Google Template
        google_yaml = """model_registry:
  gemini-2.5-flash:
    name: gemini-2.5-flash
    provider: google
    model_id: gemini-2.5-flash
    rpm: 1000
    tpm: 1000000
    pricing:
      input_per_1m_tokens: 0.30
      output_per_1m_tokens: 2.50
      per_image_input: 0.001
      per_audio_second_input: 0.00004
  
  gemini-2.5-pro:
    name: gemini-2.5-pro
    provider: google
    model_id: gemini-2.5-pro
    rpm: 150
    tpm: 2000000
    pricing:
      input_per_1m_tokens: 1.25
      output_per_1m_tokens: 10.00
      per_image_input: 0.002
      per_audio_second_input: 0.0001
  
  gemini-3.0-flash:
    name: gemini-3.0-flash
    provider: google
    model_id: gemini-3-flash-preview
    rpm: 1000
    tpm: 1000000
    pricing:
      input_per_1m_tokens: 0.50
      output_per_1m_tokens: 3.00
      per_image_input: 0.001
      per_audio_second_input: 0.00005
      per_audio_second_output: 0.0006
  
  gemini-3.0-pro:
    name: gemini-3.0-pro
    provider: google
    model_id: gemini-3-pro-preview
    rpm: 25
    tpm: 1000000
    pricing:
      input_per_1m_tokens: 2.00
      output_per_1m_tokens: 12.00
      per_image_input: 0.003
      per_audio_second_input: 0.0002
  
  gemini-2.5-flash-image:
    name: gemini-2.5-flash-image
    provider: google
    model_id: gemini-2.5-flash-image
    rpm: 100
    tpm: 100000
    pricing:
      per_image_output: 0.02
  
  gemini-3-pro-image-preview:
    name: gemini-3-pro-image-preview
    provider: google
    model_id: gemini-3-pro-image-preview
    rpm: 50
    tpm: 100000
    pricing:
      per_image_output: 0.04
  
  imagen-4.0-generate:
    name: imagen-4.0-generate
    provider: google
    model_id: imagen-4.0-generate-001
    rpm: 60
    tpm: 50000
    pricing:
      per_image_output: 0.04
  
  gemini-2.5-flash-preview-tts:
    name: gemini-2.5-flash-preview-tts
    provider: google
    model_id: gemini-2.5-flash-preview-tts
    rpm: 60
    tpm: 100000
    pricing:
      per_audio_second_output: 0.0005
      per_output_character: 0.000015
"""
        with open(os.path.join("llm.project.d", "google.yaml"), "w", encoding='utf-8') as f:
            f.write(google_yaml)
            
        # Volcengine Template
        volc_yaml = """# Volcengine (Doubao) Models
# Note: Model IDs may change with official updates. Check Volcengine console for latest versions.

model_registry:
  # 1. 深度思考 (Doubao-Seed)
  doubao-thinking:
    name: doubao-thinking
    provider: volcengine
    model_id: doubao-seed-1-6-251015  # Public model ID, may update over time
    pricing:
      input_per_1m_tokens: 0.8
      output_per_1m_tokens: 2.0
  
  # 2. DeepSeek V3 (via Volcengine)
  deepseek-v3:
    name: deepseek-v3
    provider: volcengine
    model_id: deepseek-v3-2-251201  # Public model ID, may update over time
    pricing:
      input_per_1m_tokens: 1.0
      output_per_1m_tokens: 2.0
  
  # 3. 图片生成 (Seedream)
  doubao-image:
    name: doubao-image
    provider: volcengine
    model_id: doubao-seedream-4-5-251128  # Public model ID, may update over time
    pricing:
      per_image_output: 0.02
  
  # 4. 视频生成 (Seedance)
  doubao-video:
    name: doubao-video
    provider: volcengine
    model_id: doubao-seedance-1-0-pro-250528  # Public model ID, may update over time
    pricing:
      per_video_output: 0.20  # Estimated price
"""
        with open(os.path.join("llm.project.d", "volcengine.yaml"), "w", encoding='utf-8') as f:
            f.write(volc_yaml)
            
        # Qwen Template
        qwen_yaml = """model_registry:
  qwen-max:
    name: qwen-max
    provider: dashscope
    model_id: qwen-max
    pricing:
      input_per_1m_tokens: 1.20
      output_per_1m_tokens: 6.00
  
  qwen-plus:
    name: qwen-plus
    provider: dashscope
    model_id: qwen-plus
    pricing:
      input_per_1m_tokens: 0.40
      output_per_1m_tokens: 1.20
  
  qwen-flash:
    name: qwen-flash
    provider: dashscope
    model_id: qwen-flash
    pricing:
      input_per_1m_tokens: 0.05
      output_per_1m_tokens: 0.40
  
  qwen-vl-max:
    name: qwen-vl-max
    provider: dashscope
    model_id: qwen-vl-max
    pricing:
      input_per_1m_tokens: 0.80
      output_per_1m_tokens: 2.40
      per_image_input: 0.0008
  
  qwen-audio-turbo:
    name: qwen-audio-turbo
    provider: dashscope
    model_id: qwen-audio-turbo
    pricing:
      per_audio_second_input: 0.000035
  
  qwen-image-plus:
    name: qwen-image-plus
    provider: dashscope
    model_id: qwen-image-plus
    pricing:
      per_image_output: 0.02
  
  qwen3-tts-flash:
    name: qwen3-tts-flash
    provider: dashscope
    model_id: qwen3-tts-flash
    pricing:
      per_audio_second_output: 0.0003
      per_output_character: 0.00001
  
  qwen3-asr-flash:
    name: qwen3-asr-flash
    provider: dashscope
    model_id: qwen3-asr-flash
    pricing:
      per_audio_second_input: 0.00003
"""
        with open(os.path.join("llm.project.d", "qwen.yaml"), "w", encoding='utf-8') as f:
            f.write(qwen_yaml)
            
        print("✅ Created llm.project.d/ with templates (google, volcengine, qwen)")

        # 3. User Secrets Config
        copy_template("template.user.yaml", "config.yaml", "User Config (Secrets)")
        
        # Security: Add to gitignore
        update_gitignore("config.yaml")
        
        print("\n🎉 Done! Please edit 'config.yaml' to add your API Keys.")
        return

    # Initialize Client for other commands
    try:
        client = LLMClient(project_config_path=args.project_config, user_config_path=args.user_config)
    except Exception as e:
        if args.command in ["doctor", "generate", "budget"]:
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
    elif args.command == "budget":
        from my_llm_sdk.budget.reporter import Reporter
        import json
        
        reporter = Reporter(client.budget.ledger)
        
        if args.budget_command == "status":
            summary = reporter.today_summary()
            limit = client.config.daily_spend_limit
            
            if args.json:
                data = {
                    "total_cost": summary.total_cost,
                    "request_count": summary.request_count,
                    "total_tokens": summary.total_tokens,
                    "limit": limit,
                    "percent_used": (summary.total_cost / limit * 100) if limit > 0 else 0
                }
                print(json.dumps(data, indent=2))
            else:
                print(f"📊 Today's Budget Status")
                print(f"------------------------")
                print(f"💰 Cost:       ${summary.total_cost:.4f} / ${limit:.2f}")
                print(f"🔢 Requests:   {summary.request_count}")
                print(f"🔠 Tokens:     {summary.total_tokens}")
                print(f"⚠️  Errors:     {summary.error_rate:.1%}")
                
                if limit > 0:
                    pct = (summary.total_cost / limit) * 100
                    bar_len = 20
                    filled = int(bar_len * (min(pct, 100) / 100))
                    bar = "█" * filled + "░" * (bar_len - filled)
                    print(f"\nUsage: [{bar}] {pct:.1f}%")

        elif args.budget_command == "report":
            trends = reporter.daily_trend(args.days)
            print(f"📈 Cost Trend (Last {args.days} Days)")
            print(f"------------------------------")
            max_cost = max((t.cost for t in trends), default=0)
            
            for t in trends:
                # ASCII Chart
                bar_len = 0
                if max_cost > 0:
                    bar_len = int((t.cost / max_cost) * 30)
                bar = "#" * bar_len
                print(f"{t.day} | ${t.cost:.4f} {bar}")
                
            total_cost = sum(t.cost for t in trends)
            print(f"\nTotal Cost: ${total_cost:.4f}")

        elif args.budget_command == "top":
            tops = reporter.top_consumers(args.by, args.days)
            print(f"🏆 Top Consumers by {args.by} (Last {args.days} Days)")
            print(f"{'Name':<25} | {'Cost':<10} | {'Reqs':<5}")
            print("-" * 45)
            for t in tops:
                print(f"{t.key:<25} | ${t.cost:<9.4f} | {t.reqs:<5}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()

