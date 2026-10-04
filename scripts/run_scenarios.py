import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = REPO_ROOT / "tmp"
API_CALCULATE_ENDPOINT = "http://127.0.0.1:8000/api/v1/calculate"

SCENARIOS = {
    "scenario_a_qc_bev": {
        "region": {"state_prov": "QC"},
        "fleet": {
            "vehicle_type": "school_bus_typeC",
            "vehicle_count": 10,
            "annual_mileage_per_vehicle": 12000,
            "lifecycle_years": 12,
        },
        "overrides": {},
        "climate": {},
    },
    "scenario_b_nb_comparison": {
        "region": {"state_prov": "NB"},
        "fleet": {
            "vehicle_type": "school_bus_typeC",
            "vehicle_count": 233,
            "annual_mileage_per_vehicle": 12000,
            "lifecycle_years": 12,
        },
        "overrides": {},
        "climate": {"cold_climate_flag": None},
    },
    "scenario_c_tx_cng": {
        "region": {"state_prov": "TX"},
        "fleet": {
            "vehicle_type": "school_bus_typeC",
            "vehicle_count": 25,
            "annual_mileage_per_vehicle": 15000,
            "lifecycle_years": 10,
        },
        "overrides": {},
        "climate": {},
    },
}


def run_and_save(prefix="baseline"):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for name, payload in SCENARIOS.items():
        request_body_bytes = json.dumps(payload).encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            API_CALCULATE_ENDPOINT,
            data=request_body_bytes,
            headers=request_headers,
        )

        try:
            with urllib.request.urlopen(req) as resp:
                response_bytes = resp.read()
                response_text = response_bytes.decode("utf-8")
                data = json.loads(response_text)
        except urllib.error.URLError as exc:
            print(
                f"[{prefix}] {name}: Failed to connect to {API_CALCULATE_ENDPOINT} ({exc}). "
                "Ensure the FleetPath API server is running ('uvicorn api.main:app --port 8000').",
                file=sys.stderr,
            )
            raise

        output_filename = f"{prefix}_{name}.json"
        output_file_path = TMP_DIR / output_filename
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        results[name] = data
        winner_pathway = data["verdict"]["winner_pathway"]
        pathway_currency = data["pathways"][0]["currency"]
        print(
            f"[{prefix}] {name}: saved to {output_file_path.relative_to(REPO_ROOT)} "
            f"(winner={winner_pathway}, currency={pathway_currency})"
        )

    return results


def diff_against_baseline(candidate_prefix="candidate", baseline_prefix="baseline"):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    diffs_found = False

    for name in SCENARIOS:
        baseline_file = TMP_DIR / f"{baseline_prefix}_{name}.json"
        candidate_file = TMP_DIR / f"{candidate_prefix}_{name}.json"

        if not baseline_file.exists():
            print(f"DIFF [{name}]: Baseline file {baseline_file} not found.", file=sys.stderr)
            diffs_found = True
            continue

        if not candidate_file.exists():
            print(f"DIFF [{name}]: Candidate file {candidate_file} not found.", file=sys.stderr)
            diffs_found = True
            continue

        base_content = baseline_file.read_text(encoding="utf-8")
        cand_content = candidate_file.read_text(encoding="utf-8")

        if base_content == cand_content:
            print(f"DIFF [{name}]: BYTE-IDENTICAL to baseline.")
        else:
            print(f"DIFF [{name}]: MISMATCH DETECTED between {baseline_file.name} and {candidate_file.name}!")
            diffs_found = True

    return not diffs_found


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if mode == "compare":
        cand = sys.argv[2] if len(sys.argv) > 2 else "candidate"
        base = sys.argv[3] if len(sys.argv) > 3 else "baseline"
        success = diff_against_baseline(cand, base)
        sys.exit(0 if success else 1)
    else:
        run_and_save(mode)

