# utils/plot_pareto_trace.py

import numpy as np
import plotly.graph_objects as go
import csv
from pathlib import Path


class PlotParetoTrace:
    def __init__(self, agent1_name, agent2_name, pareto_csv_path: Path, agent1_bids, agent2_bids, accepted_bid=None, title='Negotiation Bids with Estimated Opponent Utilities and Pareto Frontier Analysis'):
        self.agent1_name = agent1_name
        self.agent2_name = agent2_name
        self.pareto_points = self._load_pareto_from_csv(pareto_csv_path)
        self.agent1_bids = np.array(agent1_bids)
        self.agent2_bids = np.array(agent2_bids)
        self.accepted_bid = accepted_bid
        self.title = title
        self.fig = go.Figure()

    def _load_pareto_from_csv(self, path: Path):
        pareto = []
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                u1 = float(row['UtilityA'])
                u2 = float(row['UtilityB'])
                pareto.append((u1, u2))
        return sorted(pareto, key=lambda u: u[0])

    def plot(self):
        x = [u[0] for u in self.pareto_points]
        y = [u[1] for u in self.pareto_points]

        # Pareto frontier
        self.fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines+markers', name='Pareto Frontier',
            line=dict(color='red', width=3, dash='dash'),
            marker=dict(symbol='star', color='red', size=10, opacity=0.8),
            hovertext=[f'Pareto ({self.agent1_name}): {u1:.2f}, ({self.agent2_name}): {u2:.2f}' for u1, u2 in self.pareto_points],
            hoverinfo='text'
        ))

        # Agent 1 bids
        self.fig.add_trace(go.Scatter(
            x=self.agent1_bids[:, 0], y=self.agent1_bids[:, 1],
            mode='markers', name=f'{self.agent1_name} Bids',
            marker=dict(symbol='circle', color='blue', size=8, opacity=0.3),
            hovertext=[f'{self.agent1_name}: {u1:.2f}, {self.agent2_name}: {u2:.2f}' for u1, u2 in self.agent1_bids],
            hoverinfo='text'
        ))

        # Agent 2 bids
        self.fig.add_trace(go.Scatter(
            x=self.agent2_bids[:, 0], y=self.agent2_bids[:, 1],
            mode='markers', name=f'{self.agent2_name} Bids',
            marker=dict(symbol='square', color='green', size=8, opacity=0.3),
            hovertext=[f'{self.agent1_name}: {u1:.2f}, {self.agent2_name}: {u2:.2f}' for u1, u2 in self.agent2_bids],
            hoverinfo='text'
        ))

        if self.accepted_bid:
            self._plot_agreement()

        self._style()
        return self.fig

    def _plot_agreement(self):
        min_distance, closest_pareto = self._compute_min_pareto_distance()
        # Add legend entry for distance

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
            hovertext=[f'Accepted ({self.agent1_name}): {self.accepted_bid[0]:.2f}, ({self.agent2_name}): {self.accepted_bid[1]:.2f}'],
            hoverinfo='text'
        ))

    def _compute_min_pareto_distance(self):
        def euclidean_distance(p1, p2):
            return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

        distances = [euclidean_distance(self.accepted_bid, p) for p in self.pareto_points]
        min_distance = min(distances)
        closest_pareto = self.pareto_points[np.argmin(distances)]
        return min_distance, closest_pareto

    def _style(self):
        self.fig.update_layout(
            title=self.title,
            xaxis_title=f'Utility for {self.agent1_name} (Agent 1)',
            yaxis_title=f'Utility for {self.agent2_name} (Agent 2)',
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
