import json
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "results.json"

def compute_metrics():
    if not RESULTS_PATH.exists():
        print("❌ Error: results.json not found. Run `python evals/run_eval.py` first.")
        return

    with open(RESULTS_PATH, "r") as f:
        results = json.load(f)

    tp = fp = tn = fn = 0
    total_latency = 0.0
    ast_valid_count = 0
    total_cases = len(results)

    for r in results:
        total_latency += r["latency_seconds"]
        if r["ast_valid"]:
            ast_valid_count += 1

        is_vuln = r["is_vulnerable"]
        # A successful fix means AST is valid and pytest passed
        fix_successful = r["ast_valid"] and r["pytest_passed"]

        if is_vuln and fix_successful:
            tp += 1  # True Positive: Vulnerable code correctly fixed
        elif is_vuln and not fix_successful:
            fn += 1  # False Negative: Vulnerable code failed to fix
        elif not is_vuln and not fix_successful:
            fp += 1  # False Positive: Clean code incorrectly broken or altered
        elif not is_vuln and fix_successful:
            tn += 1  # True Negative: Clean code preserved safely

    accuracy = (tp + tn) / total_cases if total_cases > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    ast_rate = (ast_valid_count / total_cases) * 100 if total_cases > 0 else 0
    avg_latency = total_latency / total_cases if total_cases > 0 else 0

    print("\n=======================================================")
    print("📊 DEVSECOPS PIPELINE BENCHMARK METRICS SUMMARY")
    print("=======================================================")
    print(f"Total Test Scenarios Evaluated : {total_cases}")
    print(f"True Positives (Successfully Fixed) : {tp}")
    print(f"True Negatives (Clean Code Preserved): {tn}")
    print(f"False Positives (Broken/Overpatched): {fp}")
    print(f"False Negatives (Unresolved Flaws) : {fn}")
    print("-------------------------------------------------------")
    print(f"Accuracy                       : {accuracy:.4f} ({accuracy * 100:.2f}%)")
    print(f"Precision                      : {precision:.4f} ({precision * 100:.2f}%)")
    print(f"Recall (Fix Success Rate)       : {recall:.4f} ({recall * 100:.2f}%)")
    print(f"F1 Score                       : {f1_score:.4f}")
    print(f"AST Syntax Validity Rate       : {ast_rate:.2f}%")
    print(f"Average Execution Latency      : {avg_latency:.2f}s / patch")
    print("=======================================================\n")

if __name__ == "__main__":
    compute_metrics()