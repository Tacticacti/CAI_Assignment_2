import logging

class AcceptanceCondition:
    """
    Defines the acceptance strategy for the negotiation agent using a combination of:
    - AC_next: Accept if the current bid is better than the predicted next bid.
    - AC_time: Accept if we are past a specified time threshold.
    - AC_const: Accept if the bid is better than the average or max so far.

    Decision Rule:
        Accept if (AC_next) OR (AC_time AND AC_const)
    """

    def __init__(self, agent, T, use_average=True):
        """
        Initializes the acceptance condition strategy.

        Args:
            agent (DefaultParty): Reference to the negotiation agent.
            T (float): Time threshold (0 ≤ T ≤ 1) after which the agent becomes more lenient.
            use_average (bool): If True, use average utility as threshold (AC_const);
                                otherwise, use max utility.
        """
        self.agent = agent
        self.T = T
        self.use_average = use_average

        self.max_utility_received = 0.0
        self.total_utility_received = 0.0
        self.number_of_bids_received = 0

        self.last_predicted_bid_utility = None  # Cache of utility for next potential offer

    def update_received_bid_utility(self, bid_utility):
        """
        Tracks statistics on received bid utilities.

        Args:
            bid_utility (float): Utility of the newly received bid.
        """
        self.max_utility_received = max(self.max_utility_received, bid_utility)
        self.total_utility_received += bid_utility
        self.number_of_bids_received += 1

    def get_acceptance_threshold(self):
        """
        Computes the current utility threshold for acceptance.

        Returns:
            float: Either average or max utility of received bids.
        """
        if self.use_average and self.number_of_bids_received > 0:
            return self.total_utility_received / self.number_of_bids_received
        return self.max_utility_received

    def should_accept(self, bid):
        """
        Determines whether to accept the current offer.

        Combines three conditions:
        - AC_next: Is current bid better than predicted next bid?
        - AC_time: Are we past time threshold T?
        - AC_const: Is bid above average (or max) received utility?

        Args:
            bid (Bid): The bid to evaluate.

        Returns:
            bool: True if the bid should be accepted, False otherwise.
        """
        if bid is None:
            return False

        # 1. Evaluate time progress (0 to 1)
        progress = self.agent.calculate_progress()

        # 2. Evaluate bid utility
        bid_utility = self.agent.evaluate_bid(bid)
        self.update_received_bid_utility(bid_utility)

        # 3. AC_time: Check if negotiation is near the end
        time_condition_met = progress > self.T

        # 4. AC_const: Is the bid utility above our dynamic threshold?
        avg_threshold = self.get_acceptance_threshold()
        const_condition_met = bid_utility >= avg_threshold

        # 5. AC_next: Is the bid better than the predicted next offer?
        if self.last_predicted_bid_utility is None:
            self.last_predicted_bid_utility = self.agent.evaluate_bid(self.agent.find_bid())
        next_condition_met = bid_utility >= self.last_predicted_bid_utility

        # 6. Final decision
        accept_decision = next_condition_met or (time_condition_met and const_condition_met)

        # 7. Logging
        self.agent.logger.log(logging.INFO,
            f"Acceptance check: progress={progress:.2f}, "
            f"bid utility={bid_utility:.2f}, "
            f"{'AVG' if self.use_average else 'MAX'}_threshold={avg_threshold:.2f}, "
            f"AC_next={next_condition_met}, AC_time={time_condition_met}, "
            f"AC_const={const_condition_met} → Decision: {accept_decision}"
        )

        return accept_decision
