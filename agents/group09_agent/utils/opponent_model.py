from collections import defaultdict

from geniusweb.issuevalue.Bid import Bid
from geniusweb.issuevalue.DiscreteValueSet import DiscreteValueSet
from geniusweb.issuevalue.Domain import Domain
from geniusweb.issuevalue.Value import Value
import itertools
import math


def generate_rank_hypotheses(n):
    """
        Generates an array containing all possible permuations for size n.
        Each array inside is ranked from 1-n with n being the amount of issues.
    """
    # Generate a list of issue identifiers (or simply use range(1, n+1) for ranks)
    issues = list(range(1, n + 1))

    # Use itertools.permutations to generate all possible rankings (permutations)
    all_permutations = list(itertools.permutations(issues))

    # Convert permutations to a list of lists (if you want to manipulate them later)
    hypotheses_ranks = [list(permutation) for permutation in all_permutations]

    return hypotheses_ranks


class Hypothesis:
    """
        Each hypothesis keeps track of its current ranking with each rank corresponding to an issue.
        The hypothesis also keeps track of all its issue estimators.
        Each hypothesis uses a evaluation which it also keeps track of.
    """

    def __init__(self, issue_estimators, ranks, evaluation):
        self.ranks = ranks
        self.issue_estimators = issue_estimators
        self.evaluation = evaluation
        """ 
        Every hypothesis should have an indication of how well it is doing.
        Sigma range currently should be [0.01, 0.1]
        """
        # self.sigma = sigma


class OpponentModel:

    def __init__(self, domain: Domain):
        self.bids_received = []
        self.domain = domain
        self.hypotheses = []
        self.num_issues = len(domain.getIssuesValues().items())
        self.time_step = 0

        for ranking in generate_rank_hypotheses(self.num_issues):
            for eval_mode in range(3):
                hypothesis = Hypothesis(
                    {key: IssueEstimator(values) for key, values in domain.getIssuesValues().items()},
                    ranking, eval_mode)
                for idx, (issue, estimator) in enumerate(hypothesis.issue_estimators.items()):
                    estimator.updateWeight(ranking[idx], self.num_issues)
                self.hypotheses.append(hypothesis)


    def update(self, bid: Bid):
        self.bids_received.append(bid)
        for hypothesis in self.hypotheses:
            utilities = []
            for issue, estimator in hypothesis.issue_estimators.items():
                estimator.update(bid.getValue(issue), hypothesis.evaluation)
                utilities.append(estimator.get_value_utility(bid.getValue(issue)))
            self.update_rankings(hypothesis, utilities)
            """
            Here we should have a method to evaluate whether the hypothesis is going in the right direction.
            But we do not keep track when an offer gets accepted in previous deals, therefore
            we currently cannot evaluate how well a hypothesis is doing right now.
            """

    def compute_probability(self, utility, sigma, expected_value):
        factor = -((utility - expected_value) ** 2) / (2 * sigma ** 2)
        return (1 / (sigma * math.sqrt(2 * math.pi))) * math.exp(factor)

    def get_predicted_utility(self, bid: Bid):
        if not self.bids_received or bid is None:
            return 0

        utilities_list = []
        weights_list = []

        for hypothesis in self.hypotheses:
            value_scores = []
            weight_scores = []
            for issue, estimator in hypothesis.issue_estimators.items():
                value_scores.append(estimator.get_value_utility(bid.getValue(issue)))
                weight_scores.append(estimator.weight)
            utilities_list.append(value_scores)
            weights_list.append(weight_scores)

        expected_value = 1 - 0.05 * self.time_step
        sigma = 0.05
        self.time_step += 1

        hypothesis_utilities = [sum(w * v for w, v in zip(weights, values)) for weights, values in
                                zip(weights_list, utilities_list)]
        probabilities = [self.compute_probability(util, sigma, expected_value) for util in hypothesis_utilities]
        return hypothesis_utilities[probabilities.index(max(probabilities))]

    def fuzzy_similarity_bid(self, bid1: Bid, bid2: Bid) -> float:
        """
        Compute weighted similarity between two bids using issue estimators.
        Returns value in [0, 1].
        """
        if not bid1 or not bid2:
            return 0.0

        sim = 0.0
        for issue in self.domain.getIssues():
            val1 = bid1.getValue(issue)
            val2 = bid2.getValue(issue)

            # Use 1 if equal, 0 otherwise (discrete); can be extended to graded similarity
            sim_i = 1.0 if val1 == val2 else 0.0

            # Weight based on opponent's hypothesis
            weight = 0.0
            for hyp in self.hypotheses:
                if issue in hyp.issue_estimators:
                    weight += hyp.issue_estimators[issue].weight
            weight /= len(self.hypotheses)

            sim += weight * sim_i

        return sim  # No need to normalize since weights sum to 1

    # Given
    def update_rankings(self, hypothesis: Hypothesis, utility_values):
        """
        Update rankings based on utilities.

        :param utility_values: A list of utility values for each issue.
        :return: A list of updated rankings based on utilities.
        """
        sorted_indices = sorted(range(len(utility_values)), key=lambda idx: utility_values[idx], reverse=True)
        hypothesis.ranks = [0] * len(utility_values)
        for rank, index in enumerate(sorted_indices, 1):
            hypothesis.ranks[index] = rank


class IssueEstimator:
    def __init__(self, value_set: DiscreteValueSet):
        if not isinstance(value_set, DiscreteValueSet):
            raise TypeError("Only discrete value issues are supported")
        self.bids_count = 0
        self.received_values = {}
        self.total_values = value_set.size()
        self.unique_value_count = 0
        self.value_estimations = defaultdict(ValueEstimator)
        self.weight = 0

    # Updates the weight according to the corresponding rank
    def updateWeight(self, rank, total_issues):
        self.weight = (2 * rank) / (total_issues * (total_issues + 1))

    def update(self, value: Value, evaluation_mode):
        self.bids_count += 1
        if value not in self.received_values:
            self.unique_value_count += 1
            self.received_values[value] = self.unique_value_count
        self.value_estimations[value].update()
        for estimator in self.value_estimations.values():
            estimator.recalculate_utility(value, estimator.count, self.received_values, self.bids_count, evaluation_mode)

    def get_value_utility(self, value: Value):
        return self.value_estimations[value].utility if value in self.value_estimations else 0


class ValueEstimator:
    def __init__(self):
        self.count = 0
        self.utility = 0

    def update(self):
        self.count += 1

    def recalculate_utility(self, value, occurrences, received_values, total_bids, eval_type):
        if eval_type == 0:
            self.utility = received_values[value] / len(received_values)
        elif eval_type == 1:
            self.utility = 1 - received_values[value] / len(received_values)
        else:
            self.utility = occurrences / total_bids



