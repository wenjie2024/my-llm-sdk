from .checker import DiagnosticReport

def print_report(report: DiagnosticReport):
    print("\n=== Doctor Diagnostics Report ===\n")
    
    # Group by category
    grouped = {}
    for res in report.results:
        grouped.setdefault(res.category, []).append(res)
        
    for cat, items in grouped.items():
        print(f"[{cat}]")
        for item in items:
            icon = "✓" if item.status == "PASS" else ("!" if item.status == "WARN" else "✗")
            latency = f" ({item.latency_ms:.0f}ms)" if item.latency_ms > 0 else ""
            print(f"  {icon} {item.name}: {item.message}{latency}")
        print("")
        
    print("=================================\n")
