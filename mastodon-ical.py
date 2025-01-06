#!/usr/bin/env python3
import argparse
import os
import re
import sys

import requests
from ics import Calendar, Event
from mastodon import Mastodon


def remote_path_exists(url):
    try:
        # Send a HEAD request to check if the resource exists
        response = requests.head(url, allow_redirects=True)
        return response.status_code == 200  # Returns True if the status is 200 (OK)
    except requests.RequestException:
        return False  # Returns False if there's an error (e.g., network issue)


def convert_mastodon_to_ical(
    access_token,
    instance_url,
    username,
    input_file="mastodon_posts.ics",
    output_file="mastodon_posts.ics",
    limit=40,
    event_prefix="",
    event_description="",
    cutoff=40,
):
    """
    Fetch Mastodon posts and convert to iCal

    :param access_token: Mastodon API access token
    :param instance_url: Mastodon instance URL
    :param username: Target account username
    :param input_file: Path to load iCal file from
    :param output_file: Path to save iCal file
    :param limit: Number of posts to fetch
    :param event_prefix: Information prepended to event name
    :param event_description: Additional Information put into event description
    :param cutoff: Length of event names
    """
    try:
        # Initialize Mastodon client
        client = Mastodon(
            access_token=access_token,
            api_base_url=instance_url,
            ratelimit_pacefactor=1.5,
        )
        # client = Mastodon(api_base_url=instance_url, ratelimit_pacefactor=1.5)

        # Create calendar
        cal = Calendar()
        if os.path.exists(input_file):
            with open(input_file, "r") as f:
                cal = Calendar(f.read())
        elif remote_path_exists(input_file):
            cal = Calendar(requests.get(input_file).text)

        last_id = max(
            [re.findall(r"/([0-9]+)$", e.url)[0] for e in cal.events if e.url],
            default=None,
        )

        # Get account ID
        account = client.account_search(username)[0]
        user_id = account["id"]

        # Fetch posts
        posts = []
        if last_id:
            posts = client.account_statuses(
                user_id,
                exclude_replies=True,
                exclude_reblogs=True,
                since_id=last_id,
            )
        else:
            all_posts = []
            posts = client.account_statuses(
                user_id,
                exclude_replies=True,
                exclude_reblogs=True,
                limit=40,
            )

            while posts:
                all_posts.extend(posts)
                posts = client.fetch_next(posts)

            posts = all_posts

        for post in posts:
            if re.findall(r"/([0-9]+)$", post["url"])[0] == last_id:
                continue

            # Strip HTML from content
            content = re.findall(r"'(.*?)'", post["content"])
            if len(content) == 0:
                continue

            content = content[0]

            # Use post creation time
            created_at = post["created_at"]

            # Create all-day event
            event = Event()

            prefix = f"{event_prefix} : " if event_prefix else ""

            event.name = f"{prefix}{content}"
            if len(event.name) > cutoff:
                event.name = f"{event.name[:cutoff]}..."

            event.description = f"{content}\n{event_description}"

            event.url = post["url"]

            event.begin = created_at.date()
            event.make_all_day()

            cal.events.add(event)

        # Write to file
        with open(output_file, "w") as f:
            f.writelines(cal)

        print(
            f"Created iCal file with {len(cal.events)} events at {output_file} from {len(posts)} posts"
        )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Convert Mastodon posts to iCal")
    parser.add_argument("--token", required=True, help="Mastodon API access token")
    parser.add_argument("--instance", required=True, help="Mastodon instance URL")
    parser.add_argument("--username", required=True, help="Mastodon account username")
    parser.add_argument(
        "--input", default="mastodon_posts.ics", help="Input iCal file path"
    )
    parser.add_argument(
        "--output", default="mastodon_posts.ics", help="Output iCal file path"
    )
    parser.add_argument(
        "--limit", type=int, default=40, help="Number of posts to fetch"
    )
    parser.add_argument(
        "--prefix", default="", help="Information prefixing the event title"
    )
    parser.add_argument(
        "--description",
        default="",
        help="Additional Information to be put into event description beside post content",
    )
    parser.add_argument(
        "--cutoff", type=int, default=40, help="Number of characters in event title"
    )

    args = parser.parse_args()

    convert_mastodon_to_ical(
        args.token,
        args.instance,
        args.username,
        args.input,
        args.output,
        args.limit,
        args.prefix,
        args.description,
        args.cutoff,
    )


if __name__ == "__main__":
    main()
