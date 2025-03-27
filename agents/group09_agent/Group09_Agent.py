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
from .utils.plot_pareto_trace import PlotParetoTrace
from pathlib import Path

class Group09Agent(DefaultParty):
    """
    Group09Agent for the ANL 2025 negotiation assignment.

    Strategy Overview:
    - Hybrid of ABMP (time-dependent concession) and TradeOff (opponent-aware bidding).
    - Early negotiation behavior focuses on self-utility (Boulware style).
    - As time progresses, the agent considers opponent preferences via an opponent model.
    - Acceptance threshold becomes more lenient over time.
    - Bid selection balances self utility and predicted opponent utility.

    Modules Used:
    - OpponentModel (frequency + Bayesian modeling of opponent preferences)
    - AcceptanceCondition (configurable acceptance logic)
    - PlotParetoTrace (visualizing bid traces and Pareto frontier)
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
        self.result_dir: str = None

        self.last_received_bid: Bid = None
        self.opponent_model: OpponentModel = None
        self.logger.log(logging.INFO, "party is initialized")


        # Acceptance condition
        # Choose MAX_W or AVG_W by setting `use_max_w=True` or `False`
        self.T = 0.98 # Time (0 - 1) after which acceptance condition becomes more lenient
        self.acceptance_condition = AcceptanceCondition(self, self.T, use_average=False)
        self.bid_history = []

        self.last_sent_bid: Bid = None

        self.beta = 0.3  # Concession rate
        self.mu = 0.6 # Reserve



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
            self.result_dir = self.parameters.get("results_dir")




            # the profile contains the preferences of the agent over the domain
            profile_connection = ProfileConnectionFactory.create(
                data.getProfile().getURI(), self.getReporter()
            )
            self.profile = profile_connection.getProfile()
            self.domain = self.profile.getDomain()

            # profile_connection.close()

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

            # Track issue importance based on changes in issue values
            for issue_id, issue_estimator in self.opponent_model.issue_estimators.items():
                current_value = bid.getValue(issue_id)
                if issue_estimator.last_value is not None and issue_estimator.last_value != current_value:
                    issue_estimator.change_count += 1
                issue_estimator.last_value = current_value

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
            action = Accept(self.me, self.last_received_bid)

        else:
            # if not, find a bid to propose as counter offer
            bid = self.find_bid()
            # Remember to update `self.last_sent_bid` with the new bid
            self.last_sent_bid = bid
            # Log the bid before sending it
            self.log_bid(bid, str(self.me), "Offer")  # Log using the agent's own ID
            self.logger.log(logging.INFO, f"Generated new bid to offer: {bid}")
            action = Offer(self.me, bid)
        self.send_action(action)

    def save_data(self):
        """This method is called after the negotiation is finished. It can be used to store data
        for learning capabilities. Note that no extensive calculations can be done within this method.
        Taking too much time might result in your agent being killed, so use it for storage only.
        """
        data = "Data for learning (see README.md)"
        with open(f"{self.storage_dir}/data.md", "w") as f:
            f.write(data)
            #self.visualize_pareto_front()
            #print(len(self.bid_history))

    ###########################################################################################
    ################################## Helper methods below ##################################
    ###########################################################################################
    # def visualize_pareto_front(self):
    #     """
    #     Uses PlotParetoTrace to visualize bid history and the Pareto frontier,
    #     ensuring the initiator is always plotted on the x-axis.
    #     """
    #     pareto_csv_path = Path(self.parameters.get("pareto_csv"))
    #
    #     # Separate bids
    #     self_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['actor'] == str(self.me)]
    #     other_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if
    #                   b['actor'] != str(self.me)]
    #     accepted_bids = [(b['utility_self'], b['utility_opponent']) for b in self.bid_history if b['type'] == "Accept"]
    #
    #     accepted_bid = accepted_bids[-1] if accepted_bids else None
    #     # print(str(self.me))
    #     # print(str(self.other))
    #
    #     self_name = str(self.me).rsplit("_", 2)[0]
    #     other_name = str(self.other).rsplit("_", 2)[0]
    #
    #     # Get position suffixes
    #     self_position = int(str(self.me).rsplit("_", 1)[-1])
    #
    #     # Determine who is Agent 1 (odd = agent 1)
    #     if self_position % 2 == 1:
    #         agent1_name = self_name
    #         agent2_name = other_name
    #         agent1_bids = self_bids
    #         agent2_bids = other_bids
    #         accepted_bid_remapped = accepted_bid if accepted_bid else None
    #     else:
    #         agent1_name = other_name
    #         agent2_name = self_name
    #         agent1_bids = [(u_opp, u_self) for (u_self, u_opp) in other_bids]
    #         agent2_bids = [(u_opp, u_self) for (u_self, u_opp) in self_bids]
    #         accepted_bid_remapped = (accepted_bid[1], accepted_bid[0]) if accepted_bid else None
    #
    #     # Create and save plot
    #     plotter = PlotParetoTrace(
    #         agent1_name=agent1_name,
    #         agent2_name=agent2_name,
    #         pareto_csv_path=pareto_csv_path,
    #         agent1_bids=agent1_bids,
    #         agent2_bids=agent2_bids,
    #         accepted_bid=accepted_bid_remapped,
    #         title="Negotiation Bids with Estimated Opponent Utility and Pareto Frontier"
    #     )
    #
    #     fig = plotter.plot()
    #     os.makedirs(self.result_dir, exist_ok=True)
    #     filename = f"pareto_trace_plot_{agent1_name}(initiator)_vs_{agent2_name}.html"
    #     fig.write_html(Path(self.result_dir) / filename)


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
        """
            Computes the utility of a bid for this agent based on its profile.
            """
        score = self.profile.getUtility(bid)
        return float(score)

    def get_target_utility(self):
        """
        Computes the target utility based on ABMP time-dependent concession.
        """
        progress = self.calculate_progress()  # t ∈ [0,1]
        u_max = 1.0  # usually maximum utility is 1

        target = self.mu + (u_max - self.mu) * (1 - progress ** self.beta)
        return target


    def find_bid(self) -> Bid:
        """
        Finds and returns the best bid based on:
        1. Target utility (ABMP baseline)
        2. Candidate filtering within tolerance
        3. TradeOff scoring (hybrid of own + opponent utility)
        """
        all_bids = AllBidsList(self.domain)
        target_utility = self.get_target_utility()
        tolerance = 0.05

        # Step 1: Filter by iso-utility band around target
        candidate_bids = [bid for bid in all_bids if abs(self.evaluate_bid(bid) - target_utility) <= tolerance]

        # Step 2: Relax criteria if no candidates
        if not candidate_bids:
            candidate_bids = [bid for bid in all_bids if self.evaluate_bid(bid) >= target_utility]
        if not candidate_bids:
            candidate_bids = list(all_bids)
        if self.last_received_bid:
            # Step 3: Score and sort candidates
            candidate_bids.sort(key=self.score_bid, reverse=True)
        else:
            # Fallback: sort only by self utility if no info about opponent
            candidate_bids.sort(key=self.evaluate_bid, reverse=True)

        return candidate_bids[0]



    ###########################################################################################
    ################################## Example methods below ##################################
    ###########################################################################################


    def score_bid(self, bid: Bid) -> float:
        """
        Scores a bid based on a trade-off between self and opponent utility.
        Weighting dynamically shifts from self-focus (ABMP) to joint utility (TradeOff).

        Returns:
            float: heuristic score for ranking bids
        """
        progress = self.calculate_progress()
        alpha = self.dynamic_alpha()

        our_utility = self.evaluate_bid(bid)
        opponent_utility = self.opponent_model.get_predicted_utility(bid)

        time_pressure = 1.0 - progress ** (1 / self.beta)

        return alpha * time_pressure * our_utility + (1 - alpha * time_pressure) * opponent_utility

    def dynamic_alpha(self) -> float:
        """
        Returns a time-dependent weight alpha that prioritizes:
        - Self-utility early in the negotiation
        - Opponent utility later
        Starts at 1.0 (fully selfish), decreases to 0.3 as deadline approaches.
        """
        progress = self.calculate_progress()
        return max(0.3, 1.0 - self.calculate_progress())

