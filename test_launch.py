import os
import sys

# Ensure voyager is in path just in case
sys.path.append(os.path.join(os.getcwd(), 'Voyager_api', 'open-linkedin-api-main'))

from legacy.profile_extractor import launch_interactive_linkedin_login

def test_launch():
    print("Executing launch_interactive_linkedin_login...")
    res = launch_interactive_linkedin_login()
    print("Result:", res)

if __name__ == "__main__":
    test_launch()
