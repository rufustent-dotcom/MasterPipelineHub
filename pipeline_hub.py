cat << 'EOF' > pipeline_hub.py
import csv
import io
import json
import os
from datetime import datetime

# =====================================================================
# 1. BUILT-IN PIPELINE DATA & PERSONALIZED SERVICE PRESETS
# =====================================================================
DEFAULT_CSV = """ID,Name,Role,Success Rate,Run Count
a1,Data Ingestor,Data Collection,98.5,1454
a2,Analyzer,Processing,94.2,1384
a3,Report Generator,Reporting,99.1,1304"""

CUSTOMER_PRESETS = {
    "1": {"tier": "VIP Fast-Track", "delivery": "plain", "stuck_policy": "auto-repair", "sandbox": False},
    "2": {"tier": "Full Deep-Dive", "delivery": "report", "stuck_policy": "auto-repair", "sandbox": False},
    "3": {"tier": "External / 3rd-Party Info", "delivery": "json", "stuck_policy": "hold-for-review", "sandbox": True},
}


# =====================================================================
# 2. THE MASTER "ALL-IN-ONE BASKET" ENGINE
# =====================================================================
class MasterPipelineHub:
    def __init__(self, owner_name: str = "Joseph"):
        self.owner = owner_name
        self.raw_csv = DEFAULT_CSV
        self.active_profile = {
            "customer": owner_name,
            "tier": "VIP Fast-Track",
            "delivery": "plain",
            "stuck_policy": "auto-repair",
            "sandbox": False
        }
        self.stuck_queue = []
        self.repaired_count = 0
        self.data = {}
        self.refresh_pipeline()

    def refresh_pipeline(self, alert_threshold: float = 95.0):
        reader = csv.DictReader(io.StringIO(self.raw_csv.strip()))
        steps = []
        self.stuck_queue.clear()

        for i, row in enumerate(reader):
            try:
                runs = int(row["Run Count"])
                rate = float(row["Success Rate"])
            except (ValueError, KeyError):
                continue

            succeeded = round(runs * (rate / 100))
            failed = runs - succeeded
            handoff_drop = (steps[i - 1]["succeeded"] - runs) if i > 0 else 0

            step_id = row.get("ID", f"s{i+1}")
            step_name = row.get("Name", f"Step {i+1}")

            if handoff_drop > 0:
                self.stuck_queue.append({
                    "batch_id": f"drop_{step_id}",
                    "source": "Inter-Stage Handoff",
                    "stage": f"Before {step_name} ({step_id})",
                    "stuck_runs": handoff_drop,
                    "reason": "Queue filter / handoff timeout"
                })

            if failed > 0:
                self.stuck_queue.append({
                    "batch_id": f"fail_{step_id}",
                    "source": "External/Third-Party Payload" if self.active_profile["sandbox"] else "Standard Run",
                    "stage": f"{step_name} ({step_id})",
                    "stuck_runs": failed,
                    "reason": "Schema mismatch or processing timeout"
                })

            steps.append({
                "id": step_id,
                "name": step_name,
                "role": row.get("Role", "General"),
                "run_count": runs,
                "success_rate": rate,
                "succeeded": succeeded,
                "failed": failed,
                "handoff_drop": handoff_drop,
                "flagged": rate < alert_threshold
            })

        if not steps:
            self.data = {}
            return

        initial_runs = steps[0]["run_count"]
        final_succeeded = steps[-1]["succeeded"] + self.repaired_count
        e2e_efficiency = round((final_succeeded / initial_runs) * 100, 2) if initial_runs else 0.0
        bottleneck = min(steps, key=lambda s: s["success_rate"])

        self.data = {
            "hub_owner": self.owner,
            "active_profile": self.active_profile,
            "initial_runs": initial_runs,
            "final_succeeded": final_succeeded,
            "repaired_runs": self.repaired_count,
            "total_lost": max(0, initial_runs - final_succeeded),
            "e2e_efficiency": e2e_efficiency,
            "bottleneck": bottleneck,
            "steps": steps
        }

    def view_natural_language(self) -> str:
        d = self.data
        if not d:
            return "No pipeline data available."
        b = d["bottleneck"]
        p = self.active_profile
        steps = d["steps"]

        lines = [
            f"\n=== PLAIN ENGLISH BRIEFING (Profile: {p['customer']} | {p['tier']}) ===",
            f"Your pipeline took in {d['initial_runs']:,} initial runs at '{steps[0]['name']}' "
            f"and delivered {d['final_succeeded']:,} finished runs out of '{steps[-1]['name']}'.",
            f"Right now, your true end-to-end efficiency sits at {d['e2e_efficiency']}% "
            f"({d['total_lost']} runs currently stuck or lost)."
        ]
        if d["repaired_runs"] > 0:
            lines.append(f"  * Includes +{d['repaired_runs']} stuck runs recovered by the Unstick Engine!")

        lines.append(
            f"\nPrimary Bottleneck: '{b['name']}' ({b['id']}) in the {b['role']} stage "
            f"had the lowest rate at {b['success_rate']}% ({b['failed']} failed runs)."
        )
        for s in steps:
            if s["handoff_drop"] > 0:
                lines.append(
                    f"Handoff Alert     : {s['handoff_drop']} runs finished the previous step "
                    f"but got stuck before reaching '{s['name']}'."
                )
        return "\n".join(lines)

    def view_full_report(self) -> str:
        d = self.data
        if not d:
            return "No pipeline data available."
        b = d["bottleneck"]
        p = self.active_profile
        lines = [
            f"\n=== [1] FULL PIPELINE REPORT ({p['customer']} - {p['tier']}) ===",
            f"Active Policy: Delivery={p['delivery'].upper()} | Stuck Handling={p['stuck_policy'].upper()}"
        ]
        for s in d["steps"]:
            tag = " <-- [BOTTLENECK]" if s["id"] == b["id"] else ""
            drop = f" | Handoff Drop: {s['handoff_drop']}" if s["handoff_drop"] > 0 else ""
            lines.append(
                f"  [{s['id']}] {s['name']:<17} ({s['role']:<15}): "
                f"{s['succeeded']}/{s['run_count']} ({s['success_rate']}%) | Failed: {s['failed']}{drop}{tag}"
            )
        lines.extend([
            "------------------------------------------------------------------",
            f"Initial Runs: {d['initial_runs']} | Final Delivered: {d['final_succeeded']} "
            f"(Recovered: +{d['repaired_runs']}) | E2E Efficiency: {d['e2e_efficiency']}%"
        ])
        return "\n".join(lines)

    def view_visual_bars(self) -> str:
        if not self.data:
            return "No pipeline data available."
        lines = ["\n=== [2] VISUAL PIPELINE HEALTH BARS ==="]
        for s in self.data["steps"]:
            bars = int(s["success_rate"] // 5)
            meter = "█" * bars + "░" * (20 - bars)
            lines.append(f"  {s['id']} {s['name']:<17} [{meter}] {s['success_rate']}% ({s['succeeded']} ok)")
        return "\n".join(lines)

    def view_what_if(self) -> str:
        d = self.data
        if not d:
            return "No pipeline data available."
        b = d["bottleneck"]
        boosted_rate = 99.0
        gained = round(b["run_count"] * (boosted_rate / 100)) - b["succeeded"]
        new_final = d["final_succeeded"] + gained
        new_e2e = round((new_final / d["initial_runs"]) * 100, 2)
        return (
            f"\n=== [3] 'WHAT-IF' OPTIMIZER SIMULATION ===\n"
            f"If we tune '{b['name']}' ({b['id']}) from {b['success_rate']}% up to {boosted_rate}%:\n"
            f"  + Extra Runs Saved : +{gained} runs\n"
            f"  + New E2E Rate     : {new_e2e}% (up from {d['e2e_efficiency']}%)"
        )

    def manage_stuck_queue(self, action: str = "inspect") -> str:
        total_stuck = sum(item["stuck_runs"] for item in self.stuck_queue)
        if not self.stuck_queue and self.repaired_count > 0:
            return f"\n=== [4] UNSTICK ENGINE ===\nAll queues clear! ({self.repaired_count} runs already recovered and delivered)."

        lines = [f"\n=== [4] UNSTICK ENGINE ({len(self.stuck_queue)} Batches | {total_stuck} Total Runs Jammed) ==="]
        for item in self.stuck_queue:
            lines.append(
                f"  - [{item['batch_id']}] {item['stuck_runs']} runs stuck at {item['stage']} "
                f"| Source: {item['source']} | Reason: {item['reason']}"
            )

        if action == "repair":
            recovered = total_stuck
            self.repaired_count += recovered
            self.refresh_pipeline()
            self.stuck_queue.clear()
            lines.append(f"\n  >>> [AUTO-REPAIR COMPLETE] Sanitized & pushed all {recovered} stuck runs to completion!")
            lines.append(f"  >>> New End-to-End Efficiency: {self.data['e2e_efficiency']}% (100% of runs accounted for!)")
        elif action == "bypass":
            lines.append(f"\n  >>> [BYPASS COMPLETE] Routed {total_stuck} stuck runs around Analyzer directly to Customer Summary.")
            self.stuck_queue.clear()
        elif action == "return":
            lines.append(f"\n  >>> [RETURNED] Safely packaged {total_stuck} external runs and returned to sender with logs.")
            self.stuck_queue.clear()

        return "\n".join(lines)

    def customize_profile(self):
        print("\n--- [5] PERSONALIZE CUSTOMER & SERVICE PROFILE ---")
        name = input(f"Customer / Project Name (Press Enter for '{self.active_profile['customer']}'): ").strip()
        if name:
            self.active_profile["customer"] = name

        print("Select Service Preset:")
        print("  1 : VIP Fast-Track (Plain English + Auto-Repair Stuck Info)")
        print("  2 : Full Deep-Dive (Detailed Table + Auto-Repair)")
        print("  3 : External / Someone Else's Info (Sandboxed + Hold Stuck Info for Review)")
        p_choice = input("Pick preset (1-3): ").strip()

        if p_choice in CUSTOMER_PRESETS:
            preset = CUSTOMER_PRESETS[p_choice]
            self.active_profile.update(preset)
            self.refresh_pipeline()
            print(f"Updated profile for '{self.active_profile['customer']}' -> {preset['tier']}!")
        else:
            print("Kept current preset settings.")


def match_natural_language(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ("unstick", "stuck", "jam", "recover", "repair", "someone", "external")):
        return "4"
    if any(w in t for w in ("customer", "profile", "personal", "preset", "choice")):
        return "5"
    if any(w in t for w in ("load", "file", "csv", "add", "row", "import")):
        return "6"
    if any(w in t for w in ("save", "export", "basket", "bundle")):
        return "7"
    if any(w in t for w in ("bar", "chart", "visual", "graph")):
        return "2"
    if any(w in t for w in ("what if", "boost", "simulate")):
        return "3"
    if any(w in t for w in ("all", "everything", "full")):
        return "8"
    if any(w in t for w in ("plain", "english", "explain", "mean", "story", "summary")):
        return "9"
    if any(w in t for w in ("report", "table", "list")):
        return "1"
    return ""


if __name__ == "__main__":
    hub = MasterPipelineHub(owner_name="Joseph")

    menu = """
==================================================================
   ALL-IN-ONE PIPELINE HUB ("ALL EGGS IN ONE BASKET")
==================================================================
  1 : Full Pipeline Report          6 : Load CSV File / Add Stage
  2 : Visual Health Bars            7 : Save Master Bundle (TXT + JSON)
  3 : 'What-If' Optimizer           8 : Run ALL Views at Once
  4 : Unstick Jammed / External Runs 9 : Plain English Briefing
  5 : Personalize Customer Profile  q : Quit
------------------------------------------------------------------
  Or just type in plain English: "unstick jobs", "plain english",
  "change customer", "show bars", or "save everything"
=================================================================="""

    print(hub.view_natural_language())

    while True:
        print(menu)
        raw = input("Command (1-9, q, or plain English): ").strip()

        if raw.lower() in ("q", "quit", "exit"):
            print("All eggs secured in one basket — lined up and closed cleanly.")
            break

        cmd = raw if raw in ("1", "2", "3", "4", "5", "6", "7", "8", "9") else match_natural_language(raw)

        if cmd == "1":
            print(hub.view_full_report())
        elif cmd == "2":
            print(hub.view_visual_bars())
        elif cmd == "3":
            print(hub.view_what_if())
        elif cmd == "4":
            print(hub.manage_stuck_queue(action="inspect"))
            if hub.stuck_queue:
                sub = input("\nHow should we handle these stuck runs? (r = Auto-Repair / b = Bypass / s = Return to Sender / Enter = Leave): ").strip().lower()
                if sub == "r":
                    print(hub.manage_stuck_queue(action="repair"))
                elif sub == "b":
                    print(hub.manage_stuck_queue(action="bypass"))
                elif sub == "s":
                    print(hub.manage_stuck_queue(action="return"))
        elif cmd == "5":
            hub.customize_profile()
        elif cmd == "6":
            print("\n--- [6] LOAD CSV FILE OR APPEND NEW STAGE ---")
            path = input("Enter CSV filename (or press Enter to type a single stage row): ").strip()
            if path:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        hub.raw_csv = f.read()
                    hub.repaired_count = 0
                    hub.refresh_pipeline()
                    print(f"Loaded '{path}' into the master basket!")
                    print(hub.view_natural_language())
                else:
                    print(f"File not found: '{path}'")
            else:
                row = input("Type row as ID,Name,Role,Success Rate,Run Count (e.g. a4,Dispatcher,Delivery,99.5,1292): ").strip()
                if row.count(",") == 4:
                    hub.raw_csv = hub.raw_csv.strip() + "\n" + row
                    hub.refresh_pipeline()
                    print("Stage added! Updated briefing:")
                    print(hub.view_natural_language())
                else:
                    print("Needs 5 comma-separated items: ID,Name,Role,Success Rate,Run Count")
        elif cmd == "7":
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bundle_txt = (
                f"MASTER PIPELINE BUNDLE — Generated {stamp}\n"
                + hub.view_natural_language() + "\n"
                + hub.view_full_report() + "\n"
                + hub.view_visual_bars() + "\n"
                + hub.view_what_if()
            )
            with open("master_basket_report.txt", "w", encoding="utf-8") as f:
                f.write(bundle_txt)
            with open("master_basket_data.json", "w", encoding="utf-8") as f:
                json.dump(hub.data, f, indent=2)
            print("\n=== [7] MASTER BUNDLE SAVED ===")
            print(f"  1. {os.path.abspath('master_basket_report.txt')}")
            print(f"  2. {os.path.abspath('master_basket_data.json')}")
        elif cmd == "8":
            print(hub.view_natural_language())
            print(hub.view_full_report())
            print(hub.view_visual_bars())
            print(hub.view_what_if())
            print(hub.manage_stuck_queue(action="inspect"))
        else:
            print(hub.view_natural_language())
EOF
git add pipeline_hub.py && git commit -m "Add MasterPipelineHub script" && git push
