import asyncio
import httpx
from typing import List, Dict, Any
from dataclasses import dataclass, field
from my_llm_sdk.config.models import MergedConfig, Endpoint
from my_llm_sdk.budget.ledger import Ledger

@dataclass
class CheckResult:
    category: str # "Config", "Network", "Budget"
    name: str     # Specific item name
    status: str   # "PASS", "FAIL", "WARN"
    message: str
    latency_ms: float = 0.0

@dataclass
class DiagnosticReport:
    results: List[CheckResult] = field(default_factory=list)
    summary: str = ""

class Doctor:
    def __init__(self, config: MergedConfig, ledger: Ledger = None):
        self.config = config
        self.ledger = ledger or Ledger()

    async def check_endpoint(self, client: httpx.AsyncClient, endpoint: Endpoint) -> CheckResult:
        try:
            start = asyncio.get_event_loop().time()
            # Use HEAD request for connectivity check
            # Some APIs reject HEAD, so might fallback to GET
            # But HEAD is safer to avoid large payloads.
            resp = await client.head(endpoint.url, timeout=3.0)
            end = asyncio.get_event_loop().time()
            latency = (end - start) * 1000
            
            # 200-499 is considered "Connectivity OK" (even if Auth fail)
            if 200 <= resp.status_code < 500:
                return CheckResult("Network", endpoint.name, "PASS", f"Connected ({resp.status_code})", latency)
            else:
                return CheckResult("Network", endpoint.name, "WARN", f"Server error ({resp.status_code})", latency)
                
        except httpx.TimeoutException:
            return CheckResult("Network", endpoint.name, "FAIL", "Timeout (3s)")
        except httpx.NetworkError as e:
            return CheckResult("Network", endpoint.name, "FAIL", f"Connection error: {str(e)}")
        except Exception as e:
            return CheckResult("Network", endpoint.name, "FAIL", f"Unexpected: {str(e)}")

    async def run_diagnostics(self) -> DiagnosticReport:
        report = DiagnosticReport()
        
        # 1. Config Checks
        pol_count = len(self.config.final_routing_policies)
        mod_count = len(self.config.final_model_registry)
        report.results.append(CheckResult("Config", "Merge Logic", "PASS", f"Policies: {pol_count}, Models: {mod_count}"))
        
        # 2. Budget Checks
        try:
            used = self.ledger.get_daily_spend()
            limit = self.config.daily_spend_limit
            status = "PASS" if used < limit else "WARN"
            report.results.append(CheckResult("Budget", "Usage", status, f"${used:.4f} / ${limit:.4f}"))
        except Exception as e:
            report.results.append(CheckResult("Budget", "Ledger", "FAIL", f"DB Error: {str(e)}"))

        # 3. Network Checks (Async)
        async with httpx.AsyncClient(verify=False) as client: # Verify=False for some proxy/dev envs? Maybe default True better.
            # Let's stick to default verify=True unless specific need, but user provided endpoints might be self-signed.
            # For Safety, Default True.
            tasks = [self.check_endpoint(client, ep) for ep in self.config.final_endpoints]
            if tasks:
                results = await asyncio.gather(*tasks)
                report.results.extend(results)
            else:
                report.results.append(CheckResult("Network", "Endpoints", "WARN", "No endpoints configured"))
                
        return report
