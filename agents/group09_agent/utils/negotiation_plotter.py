import numpy as np
import plotly.graph_objects as go
from pathlib import Path

class NegotiationPlotter:
    def __init__(self, agent1_name, agent2_name, agent1_bids, agent2_bids, accepted_bid=None, final_bid=None):
        self.agent1_name = agent1_name
        self.agent2_name = agent2_name
        self.agent1_bids = np.array(agent1_bids)
        self.agent2_bids = np.array(agent2_bids)
        self.accepted_bid = accepted_bid
        self.final_bid = final_bid
        self.all_bids = np.vstack((self.agent1_bids, self.agent2_bids))
        self.pareto_bids = self._compute_pareto_frontier()

    def _compute_pareto_frontier(self):
        sorted_bids = self.all_bids[np.argsort(self.all_bids[:, 0])]
        pareto = []
        max_u2 = -np.inf
        for u1, u2 in sorted_bids[::-1]:
            if u2 > max_u2:
                pareto.append((u1, u2))
                max_u2 = u2
        return np.array(pareto)

    def compute_distance_to_pareto(self):
        if self.final_bid is None:
            return None
        return min(np.linalg.norm(np.array(self.final_bid) - pb) for pb in self.pareto_bids)

    def plot(self, save_path: Path):
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=self.agent1_bids[:, 0], y=self.agent1_bids[:, 1],
            mode='markers+lines', name=f'{self.agent1_name} Bids',
            marker=dict(symbol='circle', color='blue', size=8, opacity=0.6),
            hoverinfo='text',
            hovertext=[f'{self.agent1_name}: {u1:.2f}, {self.agent2_name}: {u2:.2f}' for u1, u2 in self.agent1_bids]
        ))

        fig.add_trace(go.Scatter(
            x=self.agent2_bids[:, 0], y=self.agent2_bids[:, 1],
            mode='markers+lines', name=f'{self.agent2_name} Bids',
            marker=dict(symbol='square', color='green', size=8, opacity=0.6),
            hoverinfo='text',
            hovertext=[f'{self.agent1_name}: {u1:.2f}, {self.agent2_name}: {u2:.2f}' for u1, u2 in self.agent2_bids]
        ))

        fig.add_trace(go.Scatter(
            x=self.pareto_bids[:, 0], y=self.pareto_bids[:, 1],
            mode='lines+markers', name='Pareto Frontier',
            line=dict(color='red', width=3, dash='dash'),
            marker=dict(symbol='star', color='red', size=10, opacity=0.8),
            hoverinfo='text',
            hovertext=[f'Pareto ({self.agent1_name}): {u1:.2f}, Pareto ({self.agent2_name}): {u2:.2f}' for u1, u2 in self.pareto_bids]
        ))

        if self.accepted_bid:
            fig.add_trace(go.Scatter(
                x=[self.accepted_bid[0]], y=[self.accepted_bid[1]],
                mode='markers', name='Final Agreement',
                marker=dict(symbol='hexagon', color='gold', size=14, opacity=0.9),
                hoverinfo='text',
                hovertext=[f'Accepted ({self.agent1_name}): {self.accepted_bid[0]:.2f}, ({self.agent2_name}): {self.accepted_bid[1]:.2f}']
            ))

        fig.update_layout(
            title='Negotiation Bids and Pareto Front Analysis',
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

        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(save_path))
        print(f"Plot saved at: {save_path}")