import json
import time
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

from utils.plot_trace import plot_trace
from utils.runners import run_session
from utils.runners import compute_pareto_frontier

RESULTS_DIR = Path("results", time.strftime('%Y%m%d-%H%M%S'))

# create results directory if it does not exist
if not RESULTS_DIR.exists():
    RESULTS_DIR.mkdir(parents=True)

# Settings to run a negotiation session:
#   You need to specify the classpath of 2 agents to start a negotiation. Parameters for the agent can be added as a dict (see example)
#   You need to specify the preference profiles for both agents. The first profile will be assigned to the first agent.
#   You need to specify a time deadline (is milliseconds (ms)) we are allowed to negotiate before we end without agreement
settings = {
    "agents": [
        {
            "class": "agents.ANL2022.dreamteam109_agent.dreamteam109_agent.DreamTeam109Agent",
            "parameters": {"storage_dir": "agent_storage/DreamTeam109Agent"},
        },
        # {
        #     "class": "agents.template_agent.template_agent.TemplateAgent",
        #     "parameters": {"storage_dir": "agent_storage/TemplateAgent"},
        # },
        {
            "class": "agents.group09_agent.Group09_Agent.Group09_Agent",
            "parameters": {"storage_dir": "agent_storage/Group09_Agent"},
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
        if agent1_name in actor:
            agent1_bids.append((u1, u2))
        else:
            agent2_bids.append((u1, u2))

    elif "Accept" in action:
        utilities = action["Accept"]["utilities"]
        accepted_bid = tuple(utilities.values())  # Save accepted bid utilities

# Convert bid lists to NumPy arrays
agent1_bids = np.array(agent1_bids)
agent2_bids = np.array(agent2_bids)


# Assuming pareto_points is a list of (x, y) tuples
pareto_points = compute_pareto_frontier(settings)

# Sort points by x in increasing order
pareto_points_sorted = sorted(pareto_points, key=lambda u: u[0])

# Unzip into x and y
x = [u[0] for u in pareto_points_sorted]
y = [u[1] for u in pareto_points_sorted]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=agent1_bids[:, 0], y=agent1_bids[:, 1],
    mode='markers', name=f'{agent1_name} Bids',
    marker=dict(symbol='circle', color='blue', size=8, opacity=0.6),
    hoverinfo='text',
    hovertext=[f'{agent1_name}: {u1:.2f}, {agent2_name}: {u2:.2f}' for u1, u2 in agent1_bids]
))

fig.add_trace(go.Scatter(
    x=agent2_bids[:, 0], y=agent2_bids[:, 1],
    mode='markers', name=f'{agent2_name} Bids',
    marker=dict(symbol='square', color='green', size=8, opacity=0.6),
    hoverinfo='text',
    hovertext=[f'{agent1_name}: {u1:.2f}, {agent2_name}: {u2:.2f}' for u1, u2 in agent2_bids]
))

fig.add_trace(go.Scatter(
    x=x, y=y,
    mode='lines+markers', name='Pareto Frontier',
    line=dict(color='red', width=3, dash='dash'),
    marker=dict(symbol='star', color='red', size=10, opacity=0.8),
    hoverinfo='text',
    hovertext=[f'Pareto ({agent1_name}): {u1:.2f}, Pareto ({agent2_name}): {u2:.2f}' for u1, u2 in pareto_points_sorted]
))


if accepted_bid:
    fig.add_trace(go.Scatter(
        x=[accepted_bid[0]], y=[accepted_bid[1]],
        mode='markers', name='Final Agreement',
        marker=dict(symbol='hexagon', color='gold', size=14, opacity=0.9),
        hoverinfo='text',
        hovertext=[
            f'Accepted ({agent1_name}): {accepted_bid[0]:.2f}, ({agent2_name}): {accepted_bid[1]:.2f}']
    ))

fig.update_layout(
    title='Negotiation Bids and Pareto Front Analysis',
    xaxis_title=f'Utility for {agent1_name} (Agent 1)',
    yaxis_title=f'Utility for {agent2_name} (Agent 2)',
    legend_title="Bid Types and Outcomes",
    font=dict(family="Arial, sans-serif", size=12, color="#4B0082"),
    legend=dict(y=1, x=0, orientation="h"),
    template="plotly_white",
    annotations=[dict(
        xref='paper', yref='paper', x=0.5, y=-0.2,
        xanchor='center', yanchor='top',
        text='Utility values represent the favorability for each agent. Symbols indicate bid types.',
        font=dict(family='Arial, sans-serif', size=12),
        showarrow=False
    )]
)
output_file = RESULTS_DIR.joinpath("pareto_trace_plot.html")
fig.write_html(output_file)
print(f"Saved Pareto frontier plot to: {output_file}")
