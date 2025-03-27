# utils/plot_pareto_trace.py

import numpy as np
import plotly.graph_objects as go
import csv
from pathlib import Path


class PlotParetoTrace:
    def __init__(
        self,
        trace_data: dict,
        summary_data: dict,
        pareto_csv_path: Path,
        title: str = 'Negotiation Bids with Estimated Opponent Utilities and Pareto Frontier'
    ):
        """
        Initializes and preprocesses everything from trace + summary data.
        - Extracts agent names and full identifiers
        - Processes all offers and the accepted bid
        - Loads Pareto points from CSV

        Args:
            trace_data: session_results_trace dictionary
            summary_data: session_results_summary dictionary
            pareto_csv_path: path to pareto frontier CSV file
            title: title for the plot
        """
        self.trace_data = trace_data
        self.summary_data = summary_data
        self.title = title
        self.pareto_csv_path = pareto_csv_path
        self.pareto_points = self._load_pareto_from_csv(pareto_csv_path)
        self.fig = go.Figure()

        # Extract agent names (short + full)
        self.agent1_full, self.agent2_full = self._extract_full_names()



        # Extract all utilities from trace
        self.agent1_bids, self.agent2_bids, self.accepted_bid = self._extract_bids()

        # Convert to arrays for plotting
        self.agent1_bids = np.array(self.agent1_bids)
        self.agent2_bids = np.array(self.agent2_bids)

    def _extract_full_names(self):
        """
        Extract full internal agent names from the first two Offer actions.
        - The first agent to offer is agent_1 (self.agent1_full)
        - The second distinct agent to offer is agent_2 (self.agent2_full)
        """
        self.agent1_full = None
        self.agent2_full = None

        for action in self.trace_data["actions"]:
            if "Offer" in action:
                actor = action["Offer"]["actor"]
                if self.agent1_full is None:
                    self.agent1_full = actor
                elif actor != self.agent1_full:
                    self.agent2_full = actor
                    break

        return self.agent1_full, self.agent2_full


    def _extract_bids(self):
        """Parse the negotiation trace and extract all offers + final accepted bid."""
        agent1_bids, agent2_bids = [], []
        accepted_bid = None

        for action in self.trace_data["actions"]:
            if "Offer" in action:
                utilities = action["Offer"]["utilities"]
                u1, u2 = list(utilities.values())
                actor = action["Offer"]["actor"]
                if self.agent1_full in actor:
                    agent1_bids.append((u1, u2))
                else:
                    agent2_bids.append((u1, u2))
            elif "Accept" in action:
                utilities = action["Accept"]["utilities"]
                accepted_bid = tuple(utilities.values())

        return agent1_bids, agent2_bids, accepted_bid

    def _load_pareto_from_csv(self, path: Path):
        """Loads the Pareto frontier from a CSV file."""
        pareto = []
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                u1 = float(row['UtilityA'])
                u2 = float(row['UtilityB'])
                pareto.append((u1, u2))
        return sorted(pareto, key=lambda u: u[0])

    def plot(self):
        """Main method to build and return the figure."""
        x = [u[0] for u in self.pareto_points]
        y = [u[1] for u in self.pareto_points]

        # Pareto frontier
        self.fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines+markers', name='Pareto Frontier',
            line=dict(color='red', width=3, dash='dash'),
            marker=dict(symbol='star', color='red', size=10, opacity=0.8),
            hovertext=[f'Pareto ({self.agent1_full}): {u1:.2f}, ({self.agent2_full}): {u2:.2f}' for u1, u2 in self.pareto_points],
            hoverinfo='text'
        ))
        if self.agent1_bids.size > 0:

            # Agent 1 bids
            self.fig.add_trace(go.Scatter(
                x=self.agent1_bids[:, 0], y=self.agent1_bids[:, 1],
                mode='markers', name=f'{self.agent1_full} Bids',
                marker=dict(symbol='circle', color='blue', size=8, opacity=0.3),
                hovertext=[f'{self.agent1_full}: {u1:.2f}, {self.agent2_full}: {u2:.2f}' for u1, u2 in self.agent1_bids],
                hoverinfo='text'
            ))
        if self.agent2_bids.size > 0:
            # Agent 2 bids
            self.fig.add_trace(go.Scatter(
                x=self.agent2_bids[:, 0], y=self.agent2_bids[:, 1],
                mode='markers', name=f'{self.agent2_full} Bids',
                marker=dict(symbol='square', color='green', size=8, opacity=0.3),
                hovertext=[f'{self.agent1_full}: {u1:.2f}, {self.agent2_full}: {u2:.2f}' for u1, u2 in self.agent2_bids],
                hoverinfo='text'
            ))

        if self.accepted_bid:
            self._plot_agreement()

        self._style()
        return self.fig

    def _plot_agreement(self):
        """Adds final agreement and closest Pareto point to plot."""
        min_distance, closest_pareto = self.compute_min_pareto_distance()

        self.fig.add_trace(go.Scatter(
            x=[closest_pareto[0]], y=[closest_pareto[1]],
            mode='markers', name='Closest Pareto Point',
            marker=dict(symbol='x', color='black', size=12),
            hovertext=[f'Closest Pareto: {closest_pareto[0]:.2f}, {closest_pareto[1]:.2f}'],
            hoverinfo='text'
        ))

        self.fig.add_trace(go.Scatter(
            x=[self.accepted_bid[0], closest_pareto[0]],
            y=[self.accepted_bid[1], closest_pareto[1]],
            name=f"Distance to Pareto: {min_distance:.4f}",
            mode='lines', line=dict(color='gray', dash='dot')
        ))

        self.fig.add_trace(go.Scatter(
            x=[self.accepted_bid[0]], y=[self.accepted_bid[1]],
            mode='markers', name=f'Final Agreement',
            marker=dict(symbol='hexagon', color='gold', size=14, opacity=0.9),
            hovertext=[f'Accepted ({self.agent1_full}): {self.accepted_bid[0]:.2f}, ({self.agent2_full}): {self.accepted_bid[1]:.2f}'],
            hoverinfo='text'
        ))

    def compute_min_pareto_distance(self):
        """Computes the shortest distance from accepted bid to Pareto frontier."""
        def euclidean_distance(p1, p2):
            return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

        if self.accepted_bid is None:
            return None, None

        distances = [euclidean_distance(self.accepted_bid, p) for p in self.pareto_points]
        min_distance = min(distances)
        closest_pareto = self.pareto_points[np.argmin(distances)]
        return min_distance, closest_pareto

    def _style(self):
        self.fig.update_layout(
            title=self.title,
            xaxis_title=f'Utility for {self.agent1_full} (Agent 1)',
            yaxis_title=f'Utility for {self.agent2_full} (Agent 2)',
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
