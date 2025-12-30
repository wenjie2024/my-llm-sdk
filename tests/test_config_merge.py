
import pytest
from my_llm_sdk.config.models import ProjectConfig, UserConfig, RoutingPolicy, ModelDefinition, Endpoint
from my_llm_sdk.config.loader import merge_configs

def test_merge_routing_policies_append():
    """Test that user policies are appended to project policies."""
    p_policy = RoutingPolicy(name="project-rule", strategy="priority")
    u_policy = RoutingPolicy(name="user-debug", strategy="random")
    
    project = ProjectConfig(project_name="test", routing_policies=[p_policy])
    user = UserConfig(personal_routing_policies=[u_policy])
    
    merged = merge_configs(project, user)
    
    assert len(merged.final_routing_policies) == 2
    assert merged.final_routing_policies[0].name == "project-rule"
    assert merged.final_routing_policies[1].name == "user-debug"

def test_merge_model_registry_overlay():
    """Test that Project definitions overwrite User definitions for the same key."""
    # User defines gpt-4 as 'openai-v1'
    u_model = ModelDefinition(name="gpt-4", provider="openai", model_id="gpt-4-v1")
    # Project defines gpt-4 as 'azure-secure'
    p_model = ModelDefinition(name="gpt-4", provider="azure", model_id="gpt-4-secure")
    # User has a unique model
    u_unique = ModelDefinition(name="local-llama", provider="ollama", model_id="llama3")
    
    project = ProjectConfig(project_name="test", model_registry={"gpt-4": p_model})
    user = UserConfig(personal_model_overrides={"gpt-4": u_model, "local-llama": u_unique})
    
    merged = merge_configs(project, user)
    
    # "gpt-4" should be Project's version
    assert merged.final_model_registry["gpt-4"].provider == "azure"
    # "local-llama" should persist
    assert "local-llama" in merged.final_model_registry

def test_merge_endpoints_filter_residency():
    """Test that User endpoints are filtered by Project allowed_regions."""
    ep_us = Endpoint(name="us-node", url="http://us", region="us")
    ep_eu = Endpoint(name="eu-node", url="http://eu", region="eu")
    ep_cn = Endpoint(name="cn-node", url="http://cn", region="cn")
    
    # Project only allows "us" and "eu"
    project = ProjectConfig(project_name="test", allowed_regions=["us", "eu"])
    user = UserConfig(endpoints=[ep_us, ep_eu, ep_cn])
    
    merged = merge_configs(project, user)
    
    regions = [ep.region for ep in merged.final_endpoints]
    assert "us" in regions
    assert "eu" in regions
    assert "cn" not in regions
    assert len(merged.final_endpoints) == 2

def test_merge_endpoints_no_restriction():
    """Test that if allowed_regions is empty, all endpoints are kept (assuming permissive default)."""
    ep_cn = Endpoint(name="cn-node", url="http://cn", region="cn")
    
    project = ProjectConfig(project_name="test", allowed_regions=[])
    user = UserConfig(endpoints=[ep_cn])
    
    merged = merge_configs(project, user)
    assert len(merged.final_endpoints) == 1
    assert merged.final_endpoints[0].region == "cn"
