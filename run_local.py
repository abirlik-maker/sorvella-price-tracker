"""Run the scraper on THIS computer and publish the result to GitHub.

Why: allegro.pl blocks GitHub's servers, but not a normal office/home connection.
Usage:  python run_local.py
Needs:  Python 3.10+, Git (signed in to GitHub), Google Chrome, and once:
        pip install -r requirements.txt playwright
"""
import datetime as dt
import os
import subprocess
import sys

os.environ.setdefault("BROWSER_CHANNEL", "chrome")   # the real, installed Chrome
os.environ.setdefault("HEADLESS", "0")               # visible window looks less like a bot
os.environ.setdefault("CHANNEL_BUDGET", "1500")      # up to 25 min per channel

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*cmd, check=True):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=HERE, check=check)


run("git", "pull", "--rebase", "--autostash")
run(sys.executable, "-m", "scraper.browser")
run("git", "add", "docs/data")
if run("git", "diff", "--cached", "--quiet", check=False).returncode != 0:
    run("git", "commit", "-m", f"data: {dt.date.today()} (local run)")
    run("git", "push")
else:
    print("No changes to publish.")
