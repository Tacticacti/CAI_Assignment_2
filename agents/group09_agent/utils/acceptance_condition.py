import logging

class AcceptanceCondition:
    """
    Defines the conditions under which a negotiation agent will accept a bid.
    """

    def __init__(self, agent, T, use_average=True):
        """
        Initializes the acceptance condition strategy.

        Args:
            agent (DefaultParty): The negotiation agent instance.
            T (float): The initial threshold for time-based acceptance.
            use_average (bool): Use average utility instead of max utility.
        """
        self.agent = agent
        self.T = T
        self.use_average = use_average
        self.max_utility_received = 0.0
        self.total_utility_received = 0.0
        self.number_of_bids_received = 0
        self.last_predicted_bid_utility = None  # Cache the predicted bid



    def update_received_bid_utility(self, bid_utility):
        """
        Updates utility statistics for received bids.

        Args:
            bid_utility (float): The utility of the received bid.
        """
        self.max_utility_received = max(self.max_utility_received, bid_utility)
        self.total_utility_received += bid_utility
        self.number_of_bids_received += 1

    def get_acceptance_threshold(self):
        """
        Returns the threshold utility for acceptance.

        Returns:
            float: The dynamic threshold utility.
        """
        if self.use_average and self.number_of_bids_received > 0:
            return self.total_utility_received / self.number_of_bids_received
        return self.max_utility_received



    def should_accept(self, bid):
        """
        Determines whether to accept a bid using AC_combi(0.99, AVG).

        Args:
            bid (Bid): The bid to evaluate.

        Returns:
            bool: True if the bid should be accepted, False otherwise.
        """
        if bid is None:
            return False  # Cannot accept if there is no bid.

        # Calculate the current negotiation progress (0 to 1)
        progress = self.agent.calculate_progress()

        # Utility of the received bid
        bid_utility = self.agent.evaluate_bid(bid)

        # update bid utility tracking
        self.update_received_bid_utility(bid_utility)


        # AC_time: Time-based acceptance
        time_condition_met = progress > self.T  # Only activate in the last 1% of time

        # AC_const: Accept if bid utility >= average(MAX) utility
        avg_threshold = self.get_acceptance_threshold()
        const_condition_met = bid_utility >= avg_threshold


        # AC_next: Predict the next bid's utility (cached)
        if self.last_predicted_bid_utility is None:
            self.last_predicted_bid_utility = self.agent.evaluate_bid(self.agent.find_bid())  # Cache the prediction
        next_condition_met = bid_utility >= self.last_predicted_bid_utility


        # Final Decision: AC_next OR (AC_time AND AC_const)
        accept_decision = next_condition_met or (time_condition_met and const_condition_met)

        # Log the decision
        self.agent.logger.log(logging.INFO, f"Acceptance check: progress={progress:.2f}, "
                                            f"bid utility={bid_utility:.2f}, AVG_threshold={avg_threshold:.2f}, "
                                            f"AC_next={next_condition_met}, AC_time={time_condition_met}, "
                                            f"AC_const={const_condition_met} → Decision: {accept_decision}")

        return accept_decision
