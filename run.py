import json
import time
import numpy as np
import plotly.graph_objects as go
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

domain_path = Path("domains/domain00/")
profileA = "profileA.json"
profileB = "profileB.json"
pareto_csv = domain_path / f"pareto_{Path(profileA).stem}_{Path(profileB).stem}.csv"

settings = {
    "agents": [
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
    ],
    "profiles": ["domains/domain00/profileA.json", "domains/domain00/profileB.json"],
    "deadline_time_ms": 10000,
}


# run a session and obtain results in dictionaries
session_results_trace, session_results_summary = run_session(settings)

# plot trace to html file
if not session_results_trace["error"]:
    plot_trace(session_results_trace, RESULTS_DIR.joinpath("trace_plot.html"))

# write results to file
with open(RESULTS_DIR.joinpath("session_results_trace.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(session_results_trace, indent=2))
with open(RESULTS_DIR.joinpath("session_results_summary.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(session_results_summary, indent=2))


# Extract agent names dynamically
agent1_name = session_results_summary["agent_1"]
agent2_name = session_results_summary["agent_2"]


# Full names from trace (ending with _1 or _2)
agent1_full = None
agent2_full = None
for action in session_results_trace["actions"]:
    if "Offer" in action:
        actor = action["Offer"]["actor"]
        if actor.endswith("_1"):
            agent1_full = actor
        elif actor.endswith("_2"):
            agent2_full = actor
        if agent1_full and agent2_full:
            break


# Extract final agreement (if reached)
final_bid = (session_results_summary["utility_1"], session_results_summary["utility_2"])

# Extract bid utilities from trace
agent1_bids, agent2_bids = [], []
accepted_bid = None

# Extract bid utilities from the negotiation trace
for action in session_results_trace["actions"]:
    if "Offer" in action:
        utilities = action["Offer"]["utilities"]
        u1, u2 = list(utilities.values())  # Extract utilities in order

        actor = action["Offer"]["actor"]
        if agent1_full in actor:
            agent1_bids.append((u1, u2))
        else:
            agent2_bids.append((u1, u2))

    elif "Accept" in action:
        utilities = action["Accept"]["utilities"]
        accepted_bid = tuple(utilities.values())  # Save accepted bid utilities



# Convert bid lists to NumPy arrays
agent1_bids = np.array(agent1_bids)
agent2_bids = np.array(agent2_bids)


plotter = PlotParetoTrace(
    title = 'True Utility-Based Negotiation Bids with Pareto Efficiency Visualization',
    agent1_name=agent1_name,
    agent2_name=agent2_name,
    pareto_csv_path=pareto_csv,
    agent1_bids=agent1_bids,
    agent2_bids=agent2_bids,
    accepted_bid=accepted_bid
)

fig = plotter.plot()
fig.write_html(RESULTS_DIR.joinpath("pareto_trace_plot.html"))

