import logging
from random import randint
from time import time
from typing import cast
import os
from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
from geniusweb.actions.PartyId import PartyId
from geniusweb.bidspace.AllBidsList import AllBidsList
from geniusweb.inform.ActionDone import ActionDone
from geniusweb.inform.Finished import Finished
from geniusweb.inform.Inform import Inform
from geniusweb.inform.Settings import Settings
from geniusweb.inform.YourTurn import YourTurn
from geniusweb.issuevalue.Bid import Bid
from geniusweb.issuevalue.Domain import Domain
from geniusweb.party.Capabilities import Capabilities
from geniusweb.party.DefaultParty import DefaultParty
from geniusweb.profile.utilityspace.LinearAdditiveUtilitySpace import (
    LinearAdditiveUtilitySpace,
)
from geniusweb.profileconnection.ProfileConnectionFactory import (
    ProfileConnectionFactory,
)
from geniusweb.progress.ProgressTime import ProgressTime
from geniusweb.references.Parameters import Parameters
from tudelft_utilities_logging.ReportToLogger import ReportToLogger

from .utils.opponent_model import OpponentModel
from .utils.acceptance_condition import AcceptanceCondition
import plotly.graph_objects as go
from .utils.plot_pareto_trace import PlotParetoTrace
from pathlib import Path

class Group09_Agent(DefaultParty):
    """
    Template of a Python geniusweb agent.
    """

    def __init__(self):
        super().__init__()
        self.logger: ReportToLogger = self.getReporter()

        self.domain: Domain = None
        self.parameters: Parameters = None
        self.profile: LinearAdditiveUtilitySpace = None
        self.progress: ProgressTime = None
        self.me: PartyId = None
        self.other: str = None
        self.settings: Settings = None
        self.storage_dir: str = None

        self.last_received_bid: Bid = None
        self.opponent_model: OpponentModel = None
        self.logger.log(logging.INFO, "party is initialized")


        # Acceptance condition
        # Choose MAX_W or AVG_W by setting `use_max_w=True` or `False`
        self.T = 0.8 # Time (0 - 1) after which acceptance condition becomes more lenient
        self.acceptance_condition = AcceptanceCondition(self, self.T, use_average=False)
        self.bid_history = []

        self.last_sent_bid: Bid = None

        self.beta = 0.1  # Concession rate
        self.mu = 0.8 # Reserve





    def notifyChange(self, data: Inform):
        """MUST BE IMPLEMENTED
        This is the entry point of all interaction with your agent after is has been initialised.
        How to handle the received data is based on its class type.

        Args:
            info (Inform): Contains either a request for action or information.
        """

        # a Settings message is the first message that will be send to your
        # agent containing all the information about the negotiation session.

        if isinstance(data, Settings):
            self.settings = cast(Settings, data)
            self.me = self.settings.getID()

            # progress towards the deadline has to be tracked manually through the use of the Progress object
            self.progress = self.settings.getProgress()

            self.parameters = self.settings.getParameters()

            self.storage_dir = self.parameters.get("storage_dir")



            # the profile contains the preferences of the agent over the domain
            profile_connection = ProfileConnectionFactory.create(
                data.getProfile().getURI(), self.getReporter()
            )
            self.profile = profile_connection.getProfile()
            self.domain = self.profile.getDomain()

            profile_connection.close()

        # ActionDone informs you of an action (an offer or an accept)
        # that is performed by one of the agents (including yourself).
        elif isinstance(data, ActionDone):
            action = cast(ActionDone, data).getAction()
            actor = action.getActor()
            bid = action.getBid()

            if (isinstance(action, Accept)):
                self.log_bid(bid, str(actor), "Accept")  # Ensure actor is properly identified

            # ignore action if it is our action
            if actor != self.me:
                # obtain the name of the opponent, cutting of the position ID.
                self.other = str(actor).rsplit("_", 1)[0]

                # process action done by opponent
                self.opponent_action(action)
        # YourTurn notifies you that it is your turn to act
        elif isinstance(data, YourTurn):
            # execute a turn
            self.my_turn()

        # Finished will be send if the negotiation has ended (through agreement or deadline)
        elif isinstance(data, Finished):
            self.save_data()
            # terminate the agent MUST BE CALLED
            self.logger.log(logging.INFO, "party is terminating:")
            super().terminate()
        else:
            self.logger.log(logging.WARNING, "Ignoring unknown info " + str(data))

    def getCapabilities(self) -> Capabilities:
        """MUST BE IMPLEMENTED
        Method to indicate to the protocol what the capabilities of this agent are.
        Leave it as is for the ANL 2022 competition

        Returns:
            Capabilities: Capabilities representation class
        """
        return Capabilities(
            set(["SAOP"]),
            set(["geniusweb.profile.utilityspace.LinearAdditive"]),
        )

    def send_action(self, action: Action):
        """Sends an action to the opponent(s)

        Args:
            action (Action): action of this agent
        """
        self.getConnection().send(action)

    # give a description of your agent
    def getDescription(self) -> str:
        """MUST BE IMPLEMENTED
        Returns a description of your agent. 1 or 2 sentences.

        Returns:
            str: Agent description
        """
        return "Group 09 agent for the ANL 2022 competition"

    def opponent_action(self, action):
        """Process an action that was received from the opponent.

        Args:
            action (Action): action of opponent
        """
        # if it is an offer, set the last received bid
        if isinstance(action, Offer):
            # create opponent model if it was not yet initialised
            if self.opponent_model is None:
                self.opponent_model = OpponentModel(self.domain)

            bid = cast(Offer, action).getBid()

            # update opponent model with bid
            self.opponent_model.update(bid)
            # set bid as last received
            self.last_received_bid = bid
            self.log_bid(bid, str(self.other), "Offer")  # Ensure actor is properly identified

    def my_turn(self):
        """This method is called when it is our turn. It should decide upon an action
        to perform and send this action to the opponent.
        """
        # check if the last received offer is good enough
        if self.last_received_bid and self.acceptance_condition.should_accept(self.last_received_bid):
            self.logger.log(logging.INFO, "Decided to accept the last received offer")
            self.send_action(Accept(self.me, self.last_received_bid))
        else:
            # if not, find a bid to propose as counter offer
            bid = self.find_bid()
            # Remember to update `self.last_sent_bid` with the new bid
            self.last_sent_bid = bid
            # Log the bid before sending it
            self.log_bid(bid, str(self.me), "Offer")  # Log using the agent's own ID
            self.logger.log(logging.INFO, f"Generated new bid to offer: {bid}")
            self.send_action(Offer(self.me, bid))

    def save_data(self):
        """This method is called after the negotiation is finished. It can be used to store data
        for learning capabilities. Note that no extensive calculations can be done within this method.
        Taking too much time might result in your agent being killed, so use it for storage only.
        """
        data = "Data for learning (see README.md)"
        with open(f"{self.storage_dir}/data.md", "w") as f:
            f.write(data)
            self.visualize_pareto_front()

    ###########################################################################################
    ################################## Helper methods below ##################################
    ###########################################################################################
    def visualize_pareto_front(self):
        """
        Uses PlotParetoTrace to visualize bid history and the Pareto frontier.
        """
        pareto_csv_path = Path(self.parameters.get("pareto_csv"))
        # Prepare bid arrays for plotting
        agent_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if
                      b['actor'] == str(self.me)]
        opponent_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if
                         b['actor'] == str(self.other)]
        accepted_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['type'] == "Accept"]

        # Parse agent names
        agent_name = "_".join(str(self.me).rsplit("_", 2)[-2:])
        opponent_name = "_".join(str(self.other).rsplit("_", 2)[-2:])

        # Get accepted bid (assumes only one final agreement)
        accepted_bid = accepted_bids[-1] if accepted_bids else None

        # Use PlotParetoTrace
        plotter = PlotParetoTrace(
            agent1_name=agent_name,
            agent2_name=opponent_name,
            pareto_csv_path=pareto_csv_path,
            agent1_bids=agent_bids,
            agent2_bids=opponent_bids,
            accepted_bid=accepted_bid
        )

        fig = plotter.plot()
        os.makedirs(self.storage_dir, exist_ok=True)
        fig.write_html(Path(self.storage_dir) / "pareto_trace_plot.html")

    def visualize_pareto_front2(self):
        """
            Visualizes the negotiation's bids in relation to the Pareto frontier using a Plotly scatter plot.

            This method performs Pareto efficiency analysis on the bid history and generates a visual
            representation of the agent's and opponent's offered bids against the identified Pareto optimal
            frontier. Accepted bids are also plotted to provide a complete picture of the negotiation dynamics.

            The scatter plot includes:
            - Blue dots connected by lines representing the agent's offered bids over time.
            - Green dots connected by lines representing the opponent's offered bids over time.
            - Red stars connected by dashed lines indicating the bids on the Pareto frontier.
            - Gold hexagons representing bids that were accepted by either party.

            Each point on the plot includes hover text detailing the corresponding utility values for both the
            agent and the opponent, providing an interactive way to assess the negotiation process.

            The resulting plot is saved as an HTML file within the specified storage directory and then displayed.
            """


        # Separate utilities for plotting
        agent_self_utilities, agent_opponent_utilities = zip(
            *[(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['actor'] == str(self.me)])
        opponent_self_utilities, opponent_opponent_utilities = zip(
            *[(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['actor'] == str(self.other)])


        # Adding this check to ensure there are accepted bids before trying to unpack them
        if any(b['type'] == "Accept" for b in self.bid_history):
            accept_self_utilities, accept_opponent_utilities = zip(
                *[(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['type'] == "Accept"])
        else:
            accept_self_utilities, accept_opponent_utilities = [], []

        # Create Plotly figure
        fig = go.Figure()

        # Add scatter plot for all agent bids
        fig.add_trace(go.Scatter(x=agent_self_utilities, y=agent_opponent_utilities,
                                 mode='markers+lines', name='Agent Offered Bids',
                                 marker=dict(symbol='circle', color='blue', size=10, opacity=0.5),
                                 hoverinfo='text',
                                 hovertext=[f'Utility (Agent): {u_self:.2f}, Utility (Opponent): {u_opp:.2f}' for
                                            u_self, u_opp in zip(agent_self_utilities, agent_opponent_utilities)]))

        # Add scatter plot for all opponent bids
        fig.add_trace(go.Scatter(x=opponent_self_utilities, y=opponent_opponent_utilities,
                                 mode='markers+lines', name='Opponent Offered Bids',
                                 marker=dict(symbol='circle', color='green', size=10, opacity=0.5),
                                 hoverinfo='text',
                                 hovertext=[f'Utility (Agent): {u_self:.2f}, Utility (Opponent): {u_opp:.2f}' for
                                            u_self, u_opp in
                                            zip(opponent_self_utilities, opponent_opponent_utilities)]))

        # # Add scatter plot for Pareto front
        # fig.add_trace(go.Scatter(x=pareto_self_utilities, y=pareto_opponent_utilities,
        #                          mode='markers+lines', name='Pareto Front',
        #                          line=dict(color='red', width=2, dash='dash'),
        #                          marker=dict(symbol='star', color='red', size=12, opacity=0.8),
        #                          hoverinfo='text',
        #                          hovertext=[
        #                              f'Pareto Utility (Agent): {u_self:.2f}, Pareto Utility (Opponent): {u_opp:.2f}' for
        #                              u_self, u_opp in zip(pareto_self_utilities, pareto_opponent_utilities)]))

        # Add scatter plot for accepted bids (if any)
        if accept_self_utilities and accept_opponent_utilities:  # Check to avoid plotting when there are no accepted bids
            fig.add_trace(go.Scatter(x=accept_self_utilities, y=accept_opponent_utilities,
                                     mode='markers', name='Accepted Bids',
                                     marker=dict(symbol='hexagon', color='gold', size=12, opacity=0.8),
                                     hoverinfo='text',
                                     hovertext=[f'Utility (Agent): {u_self:.2f}, Utility (Opponent): {u_opp:.2f}' for
                                                u_self, u_opp in
                                                zip(accept_self_utilities, accept_opponent_utilities)]))

        # Set figure layout
        fig.update_layout(
            title='Negotiation Bids and Pareto Front Analysis',
            xaxis_title=f'Utility for {"_".join(str(self.me).rsplit("_", 2)[-2:])} (Agent)',
            yaxis_title=f'Utility for {"_".join(str(self.other).rsplit("_", 2)[-2:])} (Opponent)',
            legend_title="Bid Types and Outcomes",
            font=dict(family="Arial, sans-serif", size=12, color="#4B0082"),  # Using a hexadecimal color code
            legend=dict(y=1, x=0, orientation="h"),
            annotations=[dict(xref='paper', yref='paper', x=0.5, y=-0.2,
                              xanchor='center', yanchor='top',
                              text='Utility values represent the outcome favorability for each participant. Symbols indicate bid types.',
                              font=dict(family='Arial, sans-serif', size=12),
                              showarrow=False)]
        )

        # Serialize and save the Pareto data as JSON

        os.makedirs(self.storage_dir, exist_ok=True)  # Ensure the directory exists
        filename = f'{self.storage_dir}/pareto_optimal_vs_offered_bids_{time()}.html'
        fig.write_html(filename)

    def log_bid(self, bid, actor, actionType):
        # create opponent model if it was not yet initialised
        if self.opponent_model is None:
            self.opponent_model = OpponentModel(self.domain)

        utility_self = self.evaluate_bid(bid)
        utility_opponent = self.opponent_model.get_predicted_utility(bid)
        self.bid_history.append({
            "type": actionType,
            "actor": str(actor),
            "utility_self": utility_self,
            "utility_opponent": utility_opponent
        })

    def calculate_progress(self) -> float:
        """Calculates the current progress of the negotiation.

        Returns:
            float: The progress of the negotiation as a float between 0 (start) and 1 (end).
        """
        progress = self.progress.get(int(time() * 1000))
        return progress  # Ensure progress is within [0, 1]


    def evaluate_bid(self, bid: Bid) -> float:
        score = self.profile.getUtility(bid)
        return float(score)


    def get_target_utility(self) -> float:

        # If it's first turn, aim for best possible utility
        if self.last_sent_bid is None or self.last_received_bid is None:
            return 1.0

        opponent_utility = self.opponent_model.get_predicted_utility(self.last_received_bid)
        own_utility = self.evaluate_bid(self.last_sent_bid)
        concession = ((1 - self.mu) / own_utility) * (opponent_utility - own_utility)

        target_utility = own_utility + concession
        return target_utility

    def find_bid(self):
        all_bids = AllBidsList(self.domain)
        target_utility = self.get_target_utility()
        tolerance = 0.05

        # 1. Generate bids near target (iso-utility band)
        candidate_bids = [bid for bid in all_bids if abs(self.evaluate_bid(bid) - target_utility) <= tolerance]

        # 2. Fallback if none found
        if not candidate_bids:
            candidate_bids = [bid for bid in all_bids if self.evaluate_bid(bid) >= target_utility]
        if not candidate_bids:
            candidate_bids = list(all_bids)

        # 3. Sort by trade-off: similarity or mutual score
        if self.last_received_bid:
            candidate_bids.sort(key=lambda b: self.compute_similarity(b, self.last_received_bid), reverse=True)
        else:
            candidate_bids.sort(key=lambda b: self.score_bid(b), reverse=True)

        self.last_sent_bid = candidate_bids[0]
        return candidate_bids[0]


    def compute_similarity(self, bid1, bid2):
        matches = sum(1 for i in bid1.getIssues() if bid1.getValue(i) == bid2.getValue(i))
        return matches / len(bid1.getIssues())

    ###########################################################################################
    ################################## Example methods below ##################################
    ###########################################################################################

    def find_bid2(self) -> Bid:
        # compose a list of all possible bids
        domain = self.profile.getDomain()
        all_bids = AllBidsList(domain)

        best_bid_score = 0.0
        best_bid = None

        # take 500 attempts to find a bid according to a heuristic score
        for _ in range(500):
            bid = all_bids.get(randint(0, all_bids.size() - 1))
            bid_score = self.score_bid(bid)
            if bid_score > best_bid_score:
                best_bid_score, best_bid = bid_score, bid

        return best_bid

    def score_bid(self, bid: Bid, alpha: float = 0.95, eps: float = 0.1) -> float:
        """Calculate heuristic score for a bid

        Args:
            bid (Bid): Bid to score
            alpha (float, optional): Trade-off factor between self interested and
                altruistic behaviour. Defaults to 0.95.
            eps (float, optional): Time pressure factor, balances between conceding
                and Boulware behaviour over time. Defaults to 0.1.

        Returns:
            float: score
        """
        progress = self.calculate_progress()

        our_utility = self.evaluate_bid(bid)

        time_pressure = 1.0 - progress ** (1 / eps)
        score = alpha * time_pressure * our_utility

        if self.opponent_model is not None:
            opponent_utility = self.opponent_model.get_predicted_utility(bid)
            opponent_score = (1.0 - alpha * time_pressure) * opponent_utility
            score += opponent_score

        return score
