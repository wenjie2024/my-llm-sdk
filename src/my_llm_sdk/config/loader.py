from typing import List, Dict
import os
import yaml
from pathlib import Path
from .models import ProjectConfig, UserConfig, MergedConfig, Endpoint, RoutingPolicy, ModelDefinition
from .exceptions import ConfigurationError

def load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def merge_configs(project: ProjectConfig, user: UserConfig) -> MergedConfig:
    """
    Merge Project and User configs with specific strategies:
    1. Routing Policies: APPEND (Project + User)
    2. Model Registry: OVERLAY (Project overrides User) -- Enforcing consistency
    3. Endpoints: FILTER (User endpoints must match Project allowed_regions)
    """
    
    # 1. Routing Policies: APPEND
    # Project policies come first (higher priority in list usually implies checks first)
    # But user might want to add custom strategies.
    # We append user policies to project policies.
    final_policies = project.routing_policies.copy()
    final_policies.extend(user.personal_routing_policies)
    
    # 2. Model Registry: OVERLAY
    # Start with User's definitions (base), then overwrite with Project's.
    # WAIT: The Spec says "Project definitions priority > User definitions".
    # So if Project defines "gpt-4", it MUST be the one used.
    # If User defines a local "llama-3-debug", it can exist if Project doesn't ban it.
    # So we start with User, then update with Project.
    final_models = user.personal_model_overrides.copy()
    final_models.update(project.model_registry)  # Project overwrites Key collisions
    
    # 3. Endpoints: FILTER
    # We only use User provided endpoints (Project usually doesn't provide secrets/urls).
    # But we check against Project's allowed_regions.
    final_endpoints: List[Endpoint] = []
    
    if not project.allowed_regions:
        # If no regions specified, allow all? Or allow none?
        # Usually implies allow all or specific default. Let's assume allow all for flexibility unless restricted.
        # But for "Residency" compliance, usually strict.
        # Let's assume if list is empty, no restriction (or restrictive?).
        # Let's implement strict: if allowed_regions defined, filter. If empty, maybe allow all?
        # Let's assume if empty list -> allow all. If not empty -> filter.
        final_endpoints = user.endpoints
    else:
        for ep in user.endpoints:
            if ep.region in project.allowed_regions:
                final_endpoints.append(ep)
            else:
                # Log warning? For now just skip.
                pass
                
    return MergedConfig(
        final_routing_policies=final_policies,
        final_model_registry=final_models,
        final_endpoints=final_endpoints,
        allow_logging=project.allow_logging,
        budget_strict_mode=project.budget_strict_mode,
        daily_spend_limit=user.daily_spend_limit,
        api_keys=user.api_keys,
        resilience=project.resilience,
        network=user.network or project.network,
        settings=project.settings
    )


def load_config(project_path: str = "llm.project.yaml", user_path: str = "~/.config/llm-sdk/config.yaml") -> MergedConfig:
    p_data = load_yaml(project_path)
    u_path_expanded = os.path.expanduser(user_path)
    u_data = load_yaml(u_path_expanded)
    
    # Env Var Overrides (Simple Example)
    # In a real app, we might walk Pydantic fields or use a library like pydantic-settings
    
    project_cfg = ProjectConfig(**p_data) if p_data else ProjectConfig(project_name="default")
    user_cfg = UserConfig(**u_data) if u_data else UserConfig()
    
    return merge_configs(project_cfg, user_cfg)
