import os
import json
import time
from instagrapi import Client
import datetime
import pytz
from instagrapi.exceptions import LoginRequired

# Basic settings
USERNAME = ""
PASSWORD = ""
TARGET_PAGE = ""
COMMENT_TEXT = "اول"
CHECK_INTERVAL = 5  # Interval in seconds for re-checking

# If you are using a proxy:
PROXY = {
    "http": "socks5://127.0.0.1:10808",
    "https": "socks5://127.0.0.1:10808",
}

# Session file name (stores the login session to avoid re-login)
SESSION_FILE = "session.json"

# Iran timezone
IRAN_TZ = pytz.timezone("Asia/Tehran")

# Time range (example: from 21:29 to 22:00)
START_TIME = datetime.time(21, 29)
END_TIME = datetime.time(22, 0)

def is_time_to_check():
    """Checks if the current time is within the desired range."""
    now = datetime.datetime.now(IRAN_TZ).time()
    return START_TIME <= now <= END_TIME

def get_client():
    """
    Initializes the Client, loads session from SESSION_FILE if available,
    otherwise logs in with credentials and saves session for future use.
    """
    cl = Client()
    # Set proxy if needed
    cl.set_proxy(PROXY["http"])

    # If a saved session file exists, load it
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        print("Loaded session from file.")

    # Check if client is already logged in
    if not cl.user_id:
        try:
            cl.login(USERNAME, PASSWORD)
            print("Logged in successfully!")
            # Save session to file
            cl.dump_settings(SESSION_FILE)
            print("Session saved to file.")
        except LoginRequired:
            print("Login failed! Check your username or password.")
            exit()
        except Exception as e:
            print(f"Error during login: {e}")
            exit()
    else:
        print("Already logged in via stored session.")
    
    return cl

def get_user_id_by_search(cl, username):
    """
    Uses the private 'search_users' method (instead of a public request)
    to retrieve the user ID by username.
    """
    results = cl.search_users(username)
    for user in results:
        if user.username.lower() == username.lower():
            return user.pk
    return None

def check_and_comment(cl, max_retries=3):
    """
    Checks if there is a new post on the target page and comments on it
    if it was posted in the last 1 minute.
    """
    for attempt in range(max_retries):
        try:
            user_id = get_user_id_by_search(cl, TARGET_PAGE)
            if not user_id:
                print("Target user not found!")
                return False

            # Get the latest posts using the private v1 API
            posts = cl.user_medias_v1(user_id, amount=1)
            if not posts:
                print("No posts found!")
                return False

            last_post = posts[0]
            post_time = last_post.taken_at.astimezone(IRAN_TZ)
            current_time = datetime.datetime.now(IRAN_TZ)

            # If the post was published in the last 180 seconds
            if (current_time - post_time).total_seconds() < 180:
                cl.media_comment(last_post.pk, COMMENT_TEXT)
                print(f"Comment '{COMMENT_TEXT}' posted successfully!")
                return True
            else:
                print("The latest post is either older than 3 minute or not new.")
                return False

        except json.JSONDecodeError:
            # If Instagram returns invalid JSON, ignore (or log) it and retry
            print("Instagram returned invalid JSON. Ignoring this error.")
            time.sleep(5)
        except Exception as e:
            print(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
            # If there's a raw response from Instagram
            if hasattr(e, 'response') and e.response:
                print("Raw Instagram response:", e.response.text)
            if attempt < max_retries - 1:
                print("Retrying in 10 seconds...")
                time.sleep(10)
            else:
                print("All attempts failed.")
                return False
    
    # If we never succeed
    return False

def main():
    cl = get_client()

    while True:
        if is_time_to_check():
            print("Checking the target page...")
            if check_and_comment(cl):
                # If a comment is posted successfully, exit the loop
                break
            # If no new post or no comment posted, wait CHECK_INTERVAL seconds before next check
            time.sleep(CHECK_INTERVAL)
        else:
            now = datetime.datetime.now(IRAN_TZ)
            # Target time for today
            today_target_time = datetime.datetime.combine(now.date(), START_TIME).replace(tzinfo=IRAN_TZ)

            if now < today_target_time:
                # We haven't reached START_TIME yet
                sleep_seconds = (today_target_time - now).total_seconds()
                minutes = int(sleep_seconds // 60)
                seconds = int(sleep_seconds % 60)
                print(f"Outside the desired time range. Current time: {now.strftime('%H:%M:%S')} | "
                      f"Waiting until {START_TIME.strftime('%H:%M')} today.")
                print(f"Sleeping for {minutes} minute(s) and {seconds} second(s)...")
                time.sleep(sleep_seconds)
            else:
                # If it's already past the time range for today, wait for tomorrow
                print("The time range has passed for today. Waiting until tomorrow...")
                tomorrow = now.date() + datetime.timedelta(days=1)
                target_time = datetime.datetime.combine(tomorrow, START_TIME).replace(tzinfo=IRAN_TZ)

                sleep_seconds = (target_time - now).total_seconds()
                minutes = int(sleep_seconds // 60)
                seconds = int(sleep_seconds % 60)

                print(f"Current time: {now.strftime('%H:%M:%S')} | Tomorrow's start: {START_TIME.strftime('%H:%M')}")
                print(f"Sleeping for {minutes} minute(s) and {seconds} second(s)...")
                time.sleep(sleep_seconds)

if __name__ == "__main__":
    main()
