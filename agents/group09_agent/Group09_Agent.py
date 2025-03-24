import logging
from random import randint
from time import time
from typing import cast

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

    ###########################################################################################
    ################################## Helper methods below ##################################
    ###########################################################################################

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
