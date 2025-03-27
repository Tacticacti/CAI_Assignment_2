import json
import time
import numpy as np
from pathlib import Path

from agents.group09_agent.utils.plot_pareto_trace import PlotParetoTrace
from utils.plot_trace import plot_trace
from utils.runners import run_session


RESULTS_DIR = Path("results", time.strftime('%Y%m%d-%H%M%S'))

# create results directory if it does not exist
if not RESULTS_DIR.exists():
    RESULTS_DIR.mkdir(parents=True)

# Settings to run a negotiation session:
#   You need to specify the classpath of 2 agents to start a negotiation. Parameters for the agent can be added as a dict (see example)
#   You need to specify the preference profiles for both agents. The first profile will be assigned to the first agent.
#   You need to specify a time deadline (is milliseconds (ms)) we are allowed to negotiate before we end without agreement
from pathlib import Path

domain_path = Path("domains/domain02/")
profileA = "profileA.json"
profileB = "profileB.json"
pareto_csv = domain_path / f"pareto_{Path(profileA).stem}_{Path(profileB).stem}.csv"

settings = {
    "agents": [
#         {
#             "class": "agents.random_agent.random_agent.RandomAgent",
# "parameters": {
#                 "storage_dir": "agent_storage/RandomAgent",
#                 "results_dir": str(RESULTS_DIR),
#             },
#         },
        {
            "class": "agents.boulware_agent.boulware_agent.BoulwareAgent",
            "parameters": {"storage_dir": "agent_storage/BoulwareAgent"},
        },
        {
            "class": "agents.group09_agent.Group09_Agent.Group09Agent",
            "parameters": {
                "storage_dir": "agent_storage/Group09Agent",
                "results_dir": str(RESULTS_DIR),
            },
        },
        # {
        #     "class": "agents.group09_agent.Group09_Agent.Group09Agent",
        #     "parameters": {
        #         "storage_dir": "agent_storage/Group09Agent",
        #         "results_dir": str(RESULTS_DIR),
        #     },
        # },
    ],
    "profiles": ["domains/domain02/profileA.json", "domains/domain02/profileB.json"],
    "deadline_time_ms": 10000,
}


# run a session and obtain results in dictionaries
session_results_trace, session_results_summary = run_session(settings)

# plot trace to html file
if not session_results_trace["error"]:
    plot_trace(session_results_trace, RESULTS_DIR.joinpath("trace_plot.html"))


plotter = PlotParetoTrace(
    trace_data=session_results_trace,
    summary_data=session_results_summary,
    pareto_csv_path=pareto_csv
)

# Distance to Pareto
distance_to_pareto, _ = plotter.compute_min_pareto_distance()
session_results_summary["distance_to_pareto"] = distance_to_pareto

# write results to file
with open(RESULTS_DIR.joinpath("session_results_trace.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(session_results_trace, indent=2))
with open(RESULTS_DIR.joinpath("session_results_summary.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(session_results_summary, indent=2))


fig = plotter.plot()
fig.write_html(RESULTS_DIR.joinpath("pareto_trace_plot.html"))




