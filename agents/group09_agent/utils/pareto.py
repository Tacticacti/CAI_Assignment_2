import os
import csv
from typing import List, Tuple, Set, cast

from uri.uri import URI
from geniusweb.bidspace.pareto.ParetoLinearAdditive import ParetoLinearAdditive
from geniusweb.issuevalue.Bid import Bid
from geniusweb.party.DefaultParty import DefaultParty
from geniusweb.profile.utilityspace.LinearAdditive import LinearAdditive
from geniusweb.profileconnection.ProfileConnectionFactory import ProfileConnectionFactory
from geniusweb.profileconnection.ProfileInterface import ProfileInterface


def compute_pareto_frontier(profile_setting: List[str]) -> List[Tuple[float, float]]:
    assert isinstance(profile_setting, list) and len(profile_setting) == 2
    profiles = dict()

    profiles_uris = [f"file:{x}" for x in profile_setting]
    for profile_url in profiles_uris:
        profile_int: ProfileInterface = ProfileConnectionFactory.create(
            URI(profile_url), DefaultParty.getReporter
        )
        profile: LinearAdditive = cast(LinearAdditive, profile_int.getProfile())
        profiles[profile_url] = profile

    pareto = ParetoLinearAdditive(list(profiles.values()))
    pareto_bids: Set[Bid] = pareto.getPoints()

    frontier_points = []
    for bid in pareto_bids:
        utils = [float(profile.getUtility(bid)) for profile in profiles.values()]
        frontier_points.append(tuple(utils))  # (u1, u2)
    pareto_points_sorted = sorted(frontier_points, key=lambda u: u[0])
    return pareto_points_sorted


if __name__ == '__main__':
    # Step 1: Change to the project root
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
    print("Current working directory:", os.getcwd())

    # Step 2: List of profile pairs to compute Pareto frontiers for
    profile_pairs = [
        ["domains/domain00/profileA.json", "domains/domain00/profileB.json"],
        ["domains/domain01/profileA.json", "domains/domain01/profileB.json"],
        ["domains/domain02/profileA.json", "domains/domain02/profileB.json"],
        # Add more pairs here if needed
    ]

    # Step 3: Loop over profile pairs
    for pair in profile_pairs:
        print(f"Computing Pareto frontier for: {pair[0]} vs {pair[1]}")
        frontier = compute_pareto_frontier(pair)

        # Get profile names and their folder (domain)
        name1 = os.path.splitext(os.path.basename(pair[0]))[0]
        name2 = os.path.splitext(os.path.basename(pair[1]))[0]
        domain_folder = os.path.dirname(pair[0])  # assumes both profiles are in the same folder

        # Ensure the folder exists
        os.makedirs(domain_folder, exist_ok=True)

        # Construct output file path
        output_file = os.path.join(domain_folder, f"pareto_{name1}_{name2}.csv")

        # Save Pareto frontier to CSV
        with open(output_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["UtilityA", "UtilityB"])
            for u1, u2 in frontier:
                writer.writerow([u1, u2])

        print(f"Saved Pareto frontier to {output_file}")
