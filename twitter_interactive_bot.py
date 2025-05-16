import tweepy
from time import sleep, time
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import sys
import getpass # For hidden input

# --- Default Global Configuration (will be overridden by user input where applicable) ---
# These act as fallbacks or defaults if user skips certain inputs or for parts not made interactive
QUERY = ""
PERFORM_RETWEET = False
PERFORM_LIKE = False
PERFORM_FOLLOW = False
MAX_RESULTS_PER_SEARCH = 10

SEARCH_INTERVAL_SUCCESS = 905
SEARCH_INTERVAL_NO_RESULTS = 300
LIKE_COOLDOWN_SECONDS = 15 * 60 + 15
FOLLOW_COOLDOWN_SECONDS = 15 * 60 + 20
RETWEET_COOLDOWN_SECONDS = 15 * 60 + 10
SLEEP_BETWEEN_BATCH_ACTIONS = 60
SHORT_SLEEP_IF_NO_ACTIONS = 10

USER_BLOCKLIST_USERNAMES = set()
NEGATIVE_KEYWORDS_IN_TEXT = []
TARGET_LANGUAGES = ["en"] # Default, can be made interactive if desired

# Persistence Files (can still use these names, will be session-specific in practice)
LIKED_TWEET_IDS_FILE = "liked_tweet_ids_interactive.txt"
RETWEETED_TWEET_IDS_FILE = "retweeted_tweet_ids_interactive.txt"
FOLLOWED_USER_IDS_FILE = "followed_user_ids_interactive.txt"
LAST_SEARCHED_ID_FILE = "last_searched_id_interactive.txt"

# Logging (can keep defaults or make configurable too)
LOG_FILE = "twitter_interactive_bot.log"
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
SLEEP_AFTER_GENERIC_API_ERROR = 60
SLEEP_AFTER_CRITICAL_ERROR_BEFORE_EXIT = 5


# --- Setup Logging (same as previous refined version) ---
numeric_log_level = getattr(logging, LOG_LEVEL.upper(), None)
if not isinstance(numeric_log_level, int):
    logging.warning(f"Invalid log level: {LOG_LEVEL}. Defaulting to INFO.")
    numeric_log_level = logging.INFO
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s")
log_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, mode='a', encoding='utf-8')
log_file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(numeric_log_level)
if logger.hasHandlers(): logger.handlers.clear()
logger.addHandler(log_file_handler)
logger.addHandler(console_handler)


# --- Helper Functions (countdown_sleep, load_ids, save_id, load_last_id, save_last_id - same as previous) ---
def countdown_sleep(seconds, message_prefix=""):
    if seconds <= 0: return
    logging.info(f"{message_prefix}Sleeping for {seconds}s...")
    for i in range(seconds, 0, -1):
        print(f"\r{message_prefix}{i}s remaining...          ", end="", flush=True)
        try: sleep(1)
        except KeyboardInterrupt: print("\rCountdown interrupted.                 ", flush=True); logging.info("Countdown sleep interrupted by user."); raise
    print("\rSleep complete.                          ", flush=True)

def load_ids_from_file(filename):
    if not os.path.exists(filename): return set()
    try:
        with open(filename, 'r', encoding='utf-8') as f: return {line.strip() for line in f if line.strip()}
    except Exception as e: logging.error(f"Error loading IDs from {filename}: {e}"); return set()

def save_id_to_file(filename, item_id):
    try:
        with open(filename, 'a', encoding='utf-8') as f: f.write(str(item_id) + '\n')
    except Exception as e: logging.error(f"Error saving ID to {filename}: {e}")

def load_last_id(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f: content = f.read().strip()
            return int(content) if content and content.isdigit() else None
        return None
    except Exception as e: logging.error(f"Error loading last searched ID from {filename}: {e}"); return None

def save_last_id(filename, id_val):
    try:
        with open(filename, 'w', encoding='utf-8') as f: f.write(str(id_val) if id_val is not None else "")
    except Exception as e: logging.error(f"Error saving last searched ID to {filename}: {e}")


# --- Global Timestamps for Action Cooldowns (used by action functions) ---
last_successful_like_timestamp = 0
last_successful_follow_timestamp = 0
last_successful_retweet_timestamp = 0


# --- User Input Functions ---
def get_credentials_interactive():
    logging.info("Requesting Twitter API credentials (input will be hidden)...")
    creds = {}
    keys_to_ask = {
        "bearer_token": "App Bearer Token",
        "consumer_key": "API Key (Consumer Key)",
        "consumer_secret": "API Secret (Consumer Secret)",
        "access_token": "Access Token",
        "access_token_secret": "Access Token Secret"
    }
    print("--- Twitter API Credentials ---")
    for key, prompt_text in keys_to_ask.items():
        while True:
            value = getpass.getpass(f"Enter your {prompt_text}: ").strip()
            if not value:
                print("Credential cannot be empty. Please try again.")
                logging.warning(f"Empty input for {prompt_text}.")
            elif ' ' in value:
                print("Credential cannot contain whitespace. Please try again.")
                logging.warning(f"Whitespace found in {prompt_text}.")
            else:
                creds[key] = value
                break
    return creds

def get_search_parameters_interactive():
    global QUERY, MAX_RESULTS_PER_SEARCH # Modifies global vars
    logging.info("Requesting search parameters...")
    print("\n--- Search Configuration ---")
    while True:
        query_input = input("Enter the search query (e.g., #alxafrica, tech news): ").strip()
        if not query_input:
            print("Search query cannot be empty.")
            continue
        if not query_input.startswith('#') and not query_input.startswith('@') and ' ' not in query_input and len(query_input) > 0:
             if input(f"Your query '{query_input}' doesn't start with '#' or '@' and is a single word. This might yield broad/irrelevant results. Continue? (y/n): ").strip().lower() != 'y':
                 continue
        QUERY = query_input
        break
    
    default_max_results = 10 # Default for Free Tier
    while True:
        try:
            num_results_str = input(f"How many results per search batch (1-100, default {default_max_results})? ").strip()
            if not num_results_str:
                MAX_RESULTS_PER_SEARCH = default_max_results
                break
            num_results = int(num_results_str)
            if 1 <= num_results <= 100:
                MAX_RESULTS_PER_SEARCH = num_results
                break
            else:
                print(f"Please enter a number between 1 and 100. Free tier usually works best with <= {default_max_results}.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    logging.info(f"Search query: '{QUERY}', Max results per batch: {MAX_RESULTS_PER_SEARCH}")

def get_action_preferences_interactive():
    global PERFORM_RETWEET, PERFORM_LIKE, PERFORM_FOLLOW
    logging.info("Requesting action preferences...")
    print("\n--- Action Preferences (y/n) ---")
    PERFORM_RETWEET = input("Enable Retweet action? (default n): ").strip().lower() == 'y'
    PERFORM_LIKE = input("Enable Like action? (default n): ").strip().lower() == 'y'
    PERFORM_FOLLOW = input("Enable Follow action? (default n): ").strip().lower() == 'y'
    logging.info(f"Actions - Retweet: {PERFORM_RETWEET}, Like: {PERFORM_LIKE}, Follow: {PERFORM_FOLLOW}")

def get_filter_preferences_interactive():
    global USER_BLOCKLIST_USERNAMES, NEGATIVE_KEYWORDS_IN_TEXT
    logging.info("Requesting filter preferences...")
    print("\n--- Content & User Filtering ---")
    
    block_input = input("Enter usernames to blocklist (comma-separated, e.g., user1,user2) or leave blank: ").strip()
    if block_input:
        USER_BLOCKLIST_USERNAMES = {name.strip().lower().lstrip('@') for name in block_input.split(',') if name.strip()}
    else:
        USER_BLOCKLIST_USERNAMES = set() # Ensure it's an empty set if blank
    
    keyword_input = input("Enter negative keywords/phrases to skip (comma-separated) or leave blank: ").strip()
    if keyword_input:
        NEGATIVE_KEYWORDS_IN_TEXT = [keyword.strip().lower() for keyword in keyword_input.split(',') if keyword.strip()]
    else:
        NEGATIVE_KEYWORDS_IN_TEXT = [] # Ensure it's an empty list if blank

    logging.info(f"User Blocklist: {USER_BLOCKLIST_USERNAMES if USER_BLOCKLIST_USERNAMES else 'None'}")
    logging.info(f"Negative Keywords: {NEGATIVE_KEYWORDS_IN_TEXT if NEGATIVE_KEYWORDS_IN_TEXT else 'None'}")

# --- Modified Twitter API Action Functions ---
# These now use the global config variables set by user input
# and take session-specific persistence sets and filenames as arguments

def initialize_client_and_get_me(creds_dict): # Takes credentials dictionary
    try:
        client = tweepy.Client(
            bearer_token=creds_dict['bearer_token'],
            consumer_key=creds_dict['consumer_key'],
            consumer_secret=creds_dict['consumer_secret'],
            access_token=creds_dict['access_token'],
            access_token_secret=creds_dict['access_token_secret']
        )
        logging.info("Successfully initialized tweepy.Client with provided credentials.")
        me_response = client.get_me(user_fields=['id', 'username'])
        if me_response.data:
            my_id = me_response.data.id
            my_username = me_response.data.username
            logging.info(f"Authenticated as: @{my_username} (ID: {my_id})")
            return client, my_id, my_username
        else:
            logging.critical(f"Could not get 'me' data using provided credentials. Errors: {me_response.errors}")
            return None, None, None
    except KeyError as e:
        logging.critical(f"Missing credential key: {e}. Please provide all required credentials.")
        return None, None, None
    except tweepy.TweepyException as e:
        logging.critical(f"Failed to initialize client or authenticate: {e}")
        return None, None, None
    except Exception as e:
        logging.critical(f"Unexpected error during client init: {e}")
        return None, None, None

def perform_search_interactive(client, current_query, current_since_id, current_max_results): # Uses interactive params
    logging.info(f"Searching for tweets with: '{current_query}' (since_id: {current_since_id}, max_results: {current_max_results})")
    try:
        response = client.search_recent_tweets(
            current_query,
            max_results=current_max_results,
            since_id=current_since_id,
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'text', 'referenced_tweets', 'lang'],
            expansions=['author_id', 'referenced_tweets.id', 'referenced_tweets.id.author_id'],
            user_fields=['username', 'name', 'verified']
        )
        return response
    except tweepy.TooManyRequests as tmr:
        logging.warning(f"Search rate limit hit: {tmr}.") # Removed "Will sleep..." as main loop handles it
        raise 
    except tweepy.TweepyException as e:
        logging.error(f"Error during search: {e}")
        return None

def should_skip_tweet_interactive(tweet_text, tweet_author_username, tweet_lang=None): # Uses global filters
    # Uses global TARGET_LANGUAGES, NEGATIVE_KEYWORDS_IN_TEXT, USER_BLOCKLIST_USERNAMES
    if TARGET_LANGUAGES and tweet_lang and tweet_lang.lower() not in [lang.lower() for lang in TARGET_LANGUAGES]:
        logging.info(f"Skipping tweet: Language '{tweet_lang}' not in target languages {TARGET_LANGUAGES}.")
        return True
    if any(keyword.lower() in tweet_text.lower() for keyword in NEGATIVE_KEYWORDS_IN_TEXT):
        logging.info(f"Skipping tweet: Contains negative keyword. Text: {tweet_text[:100]}...")
        return True
    if tweet_author_username.lower() in (name.lower() for name in USER_BLOCKLIST_USERNAMES):
        logging.info(f"Skipping tweet: Author @{tweet_author_username} is in blocklist.")
        return True
    return False

def attempt_retweet_action_interactive(client, tweet_id, is_already_retweeted_by_other, current_retweeted_ids_set, current_retweeted_ids_file):
    global last_successful_retweet_timestamp
    tweet_id_str = str(tweet_id)
    if not PERFORM_RETWEET: return False
    if is_already_retweeted_by_other:
        logging.info(f"Skipping retweet for {tweet_id_str}: Search result was already a retweet.")
        return False
    if tweet_id_str in current_retweeted_ids_set:
        logging.info(f"Skipping retweet for {tweet_id_str}: Already retweeted in this session/persistence.")
        return False

    time_since_last_rt = time() - last_successful_retweet_timestamp
    if time_since_last_rt < RETWEET_COOLDOWN_SECONDS:
        remaining_cooldown = RETWEET_COOLDOWN_SECONDS - time_since_last_rt
        logging.info(f"Skipping retweet for {tweet_id_str}: Still in retweet cooldown period ({int(remaining_cooldown)}s remaining).")
        return False
    try:
        logging.info(f"Attempting to retweet tweet ID: {tweet_id_str}")
        client.retweet(tweet_id)
        logging.info(f"Successfully retweeted tweet ID: {tweet_id_str}")
        current_retweeted_ids_set.add(tweet_id_str)
        save_id_to_file(current_retweeted_ids_file, tweet_id_str)
        last_successful_retweet_timestamp = time()
        return True
    except tweepy.TooManyRequests:
        logging.warning(f"Rate limit hit for retweeting {tweet_id_str}. Cooldown will apply.")
        last_successful_retweet_timestamp = time()
        return False
    except tweepy.TweepyException as e:
        logging.warning(f"Error retweeting {tweet_id_str}: {e}")
        error_message = str(e).lower()
        if "already retweeted" in error_message or "you have already retweeted this tweet" in error_message:
            logging.info(f"Confirmed already retweeted (by API error) tweet ID: {tweet_id_str}")
            current_retweeted_ids_set.add(tweet_id_str)
            save_id_to_file(current_retweeted_ids_file, tweet_id_str)
        return False
    return False

def attempt_like_action_interactive(client, tweet_id, current_liked_ids_set, current_liked_ids_file):
    global last_successful_like_timestamp
    tweet_id_str = str(tweet_id)
    if not PERFORM_LIKE: return False
    if tweet_id_str in current_liked_ids_set:
        logging.info(f"Skipping like for {tweet_id_str}: Already liked in this session/persistence.")
        return False

    time_since_last_like = time() - last_successful_like_timestamp
    if time_since_last_like < LIKE_COOLDOWN_SECONDS:
        remaining_cooldown = LIKE_COOLDOWN_SECONDS - time_since_last_like
        logging.info(f"Skipping like for {tweet_id_str}: Still in like cooldown period ({int(remaining_cooldown)}s remaining).")
        return False
    try:
        logging.info(f"Attempting to like tweet ID: {tweet_id_str}")
        client.like(tweet_id)
        logging.info(f"Successfully liked tweet ID: {tweet_id_str}")
        current_liked_ids_set.add(tweet_id_str)
        save_id_to_file(current_liked_ids_file, tweet_id_str)
        last_successful_like_timestamp = time()
        return True
    except tweepy.TooManyRequests:
        logging.warning(f"Rate limit hit for liking {tweet_id_str}. Cooldown will apply.")
        last_successful_like_timestamp = time()
        return False
    except tweepy.TweepyException as e:
        logging.warning(f"Error liking {tweet_id_str}: {e}")
        error_message = str(e).lower()
        if "already liked" in error_message or "you have already liked this tweet" in error_message:
            logging.info(f"Confirmed already liked (by API error) tweet ID: {tweet_id_str}")
            current_liked_ids_set.add(tweet_id_str)
            save_id_to_file(current_liked_ids_file, tweet_id_str)
        return False
    return False

def attempt_follow_action_interactive(client, user_id_to_follow, user_username_to_follow, my_bot_id, current_followed_ids_set, current_followed_ids_file):
    global last_successful_follow_timestamp
    user_id_str = str(user_id_to_follow)
    if not PERFORM_FOLLOW or user_id_to_follow == my_bot_id:
        if user_id_to_follow == my_bot_id: logging.info("Skipping follow: Cannot follow self.")
        return False
    if user_id_str in current_followed_ids_set:
        logging.info(f"Skipping follow for @{user_username_to_follow}: Already followed in this session/persistence.")
        return False

    time_since_last_follow = time() - last_successful_follow_timestamp
    if time_since_last_follow < FOLLOW_COOLDOWN_SECONDS:
        remaining_cooldown = FOLLOW_COOLDOWN_SECONDS - time_since_last_follow
        logging.info(f"Skipping follow for @{user_username_to_follow}: Still in follow cooldown period ({int(remaining_cooldown)}s remaining).")
        return False
    try:
        logging.info(f"Attempting to follow user @{user_username_to_follow} (ID: {user_id_str})")
        client.follow_user(target_user_id=user_id_to_follow)
        logging.info(f"Successfully followed user @{user_username_to_follow} (ID: {user_id_str})")
        current_followed_ids_set.add(user_id_str)
        save_id_to_file(current_followed_ids_file, user_id_str)
        last_successful_follow_timestamp = time()
        return True
    except tweepy.TooManyRequests:
        logging.warning(f"Rate limit hit for following @{user_username_to_follow}. Cooldown will apply.")
        last_successful_follow_timestamp = time()
        return False
    except tweepy.TweepyException as e:
        logging.warning(f"Error following @{user_username_to_follow}: {e}")
        return False
    return False

# --- Main Interactive Bot Loop ---
def main_interactive_loop():
    # 1. Get User Inputs
    user_creds = get_credentials_interactive()
    get_search_parameters_interactive()
    get_action_preferences_interactive()
    get_filter_preferences_interactive()

    # 2. Initialize Client
    client, my_bot_id, my_bot_username = initialize_client_and_get_me(user_creds)
    if not client:
        logging.error("Exiting due to authentication failure.")
        return

    # 3. Load session-specific persistence
    session_liked_ids = load_ids_from_file(LIKED_TWEET_IDS_FILE)
    session_retweeted_ids = load_ids_from_file(RETWEETED_TWEET_IDS_FILE)
    session_followed_ids = load_ids_from_file(FOLLOWED_USER_IDS_FILE)
    current_last_searched_id = load_last_id(LAST_SEARCHED_ID_FILE)

    logging.info("--- Bot Starting with User Configuration ---")
    # ... (logging of settings as before) ...
    logging.info(f"Loaded {len(session_liked_ids)} liked, {len(session_retweeted_ids)} retweeted, {len(session_followed_ids)} followed IDs for this session.")
    logging.info(f"Starting since_id for search: {current_last_searched_id if current_last_searched_id else 'None (fetching latest)'}")
    logging.info("------------------------------------------")
    
    global last_successful_like_timestamp, last_successful_follow_timestamp, last_successful_retweet_timestamp
    last_successful_like_timestamp = 0
    last_successful_follow_timestamp = 0
    last_successful_retweet_timestamp = 0

    while True:
        try:
            response = perform_search_interactive(client, QUERY, current_last_searched_id, MAX_RESULTS_PER_SEARCH)
            if not response:
                countdown_sleep(SEARCH_INTERVAL_NO_RESULTS, "Search failed/no response. Retrying: ")
                continue

            new_highest_id_this_batch = current_last_searched_id
            tweets_found_in_batch = 0
            action_attempted_in_overall_batch = False

            if response.data:
                tweets_found_in_batch = len(response.data)
                logging.info(f"Found {tweets_found_in_batch} tweets in search results.")

                users = {user["id"]: user for user in response.includes.get("users", [])}
                original_tweets_data = {tweet["id"]: tweet for tweet in response.includes.get("tweets", [])}

                for search_result_tweet in response.data:
                    action_attempted_this_tweet_cycle = False

                    if new_highest_id_this_batch is None or search_result_tweet.id > new_highest_id_this_batch:
                        new_highest_id_this_batch = search_result_tweet.id
                    
                    author_id = search_result_tweet.author_id
                    author_username = users.get(author_id, {}).get("username", "UnknownUser")
                    tweet_lang = getattr(search_result_tweet, 'lang', None)
                    
                    # --- MODIFIED LOGGING LINE TO INCLUDE TWEET TEXT ---
                    # Truncate text if too long for a log line, or replace newlines
                    tweet_text_for_log = search_result_tweet.text.replace('\n', ' ').strip()
                    if len(tweet_text_for_log) > 150: # Max length for log preview
                        tweet_text_for_log = tweet_text_for_log[:147] + "..."

                    logging.info(f"--- Processing Search Result ID: {search_result_tweet.id} by @{author_username} --- Text: \"{tweet_text_for_log}\" ---")
                    # --- END OF MODIFIED LOGGING LINE ---
                    
                    logging.debug(f"Full raw tweet text: {search_result_tweet.text}") # Keep full text in debug

                    if author_id == my_bot_id:
                        logging.info("Skipping: Search result is by the bot itself.")
                    elif should_skip_tweet_interactive(search_result_tweet.text, author_username, tweet_lang):
                        pass 
                    else:
                        target_tweet_for_interaction = search_result_tweet
                        user_to_follow_id = author_id
                        user_to_follow_username = author_username
                        is_a_retweet_by_another_user = False

                        if search_result_tweet.referenced_tweets:
                            for ref in search_result_tweet.referenced_tweets:
                                if ref.type == 'retweeted':
                                    is_a_retweet_by_another_user = True
                                    if ref.id in original_tweets_data:
                                        target_tweet_for_interaction = original_tweets_data[ref.id]
                                        user_to_follow_id = target_tweet_for_interaction.author_id
                                        user_to_follow_username = users.get(user_to_follow_id, {}).get("username", "OriginalUnknown")
                                        logging.info(f"This is an RT. Targeting original tweet {target_tweet_for_interaction.id} by @{user_to_follow_username}")
                                    else:
                                        logging.warning(f"RT detected, but original tweet {ref.id} not in expansions. Will target RT object.")
                                    break
                        
                        if target_tweet_for_interaction.author_id == my_bot_id:
                            logging.info("Skipping actions: Target tweet (original or search result) is by the bot itself.")
                        else:
                            if attempt_retweet_action_interactive(client, target_tweet_for_interaction.id, is_a_retweet_by_another_user, session_retweeted_ids, RETWEETED_TWEET_IDS_FILE):
                                action_attempted_this_tweet_cycle = True
                            if attempt_like_action_interactive(client, target_tweet_for_interaction.id, session_liked_ids, LIKED_TWEET_IDS_FILE):
                                action_attempted_this_tweet_cycle = True
                            if attempt_follow_action_interactive(client, user_to_follow_id, user_to_follow_username, my_bot_id, session_followed_ids, FOLLOWED_USER_IDS_FILE):
                                action_attempted_this_tweet_cycle = True
                    
                    sleep_duration_after_tweet = SHORT_SLEEP_IF_NO_ACTIONS
                    if action_attempted_this_tweet_cycle:
                        action_attempted_in_overall_batch = True
                        sleep_duration_after_tweet = SLEEP_BETWEEN_BATCH_ACTIONS
                    
                    if sleep_duration_after_tweet > 0:
                         countdown_sleep(sleep_duration_after_tweet, f"Post-tweet {search_result_tweet.id} delay: ")

                if new_highest_id_this_batch and (current_last_searched_id is None or new_highest_id_this_batch > current_last_searched_id):
                    current_last_searched_id = new_highest_id_this_batch
                    logging.info(f"Updating last_searched_id to: {current_last_searched_id}")
                    save_last_id(LAST_SEARCHED_ID_FILE, current_last_searched_id)
            else:
                logging.info("No new tweets found in this search iteration.")

            sleep_interval_before_next_search = SEARCH_INTERVAL_NO_RESULTS
            if tweets_found_in_batch > 0 or action_attempted_in_overall_batch:
                sleep_interval_before_next_search = SEARCH_INTERVAL_SUCCESS
            
            countdown_sleep(sleep_interval_before_next_search, "Next search batch in: ")

        # ... (except blocks for TooManyRequests, TweepyException, KeyboardInterrupt, Exception as before) ...
        except tweepy.TooManyRequests as tmr_main:
            logging.error(f"Main loop caught TooManyRequests (likely search): {tmr_main}.")
            rate_limit_sleep_duration = SEARCH_INTERVAL_SUCCESS + 60 # Add buffer
            try:
                countdown_sleep(rate_limit_sleep_duration, "Search rate limit cooldown: ")
            except KeyboardInterrupt:
                logging.info("Bot stopped by user during search rate limit sleep.")
                if 'current_last_searched_id' in locals() and current_last_searched_id: # Check if defined
                    save_last_id(LAST_SEARCHED_ID_FILE, current_last_searched_id)
                break 
        except tweepy.TweepyException as e_main:
            logging.error(f"A Tweepy API error occurred in main loop: {e_main}")
            if hasattr(e_main, 'response') and e_main.response is not None:
                logging.error(f"Response details: Status {e_main.response.status_code}, Text: {e_main.response.text[:200]}")
            countdown_sleep(SLEEP_AFTER_GENERIC_API_ERROR, "Waiting after API error: ")
        except KeyboardInterrupt:
            logging.info("Bot stopped by user (KeyboardInterrupt).")
            if 'current_last_searched_id' in locals() and current_last_searched_id: # Check if defined
                save_last_id(LAST_SEARCHED_ID_FILE, current_last_searched_id)
            break
        except Exception as e_unexpected:
            logging.critical(f"An UNEXPECTED error occurred in main loop: {e_unexpected}")
            logging.critical(traceback.format_exc())
            if 'current_last_searched_id' in locals() and current_last_searched_id: # Check if defined
                save_last_id(LAST_SEARCHED_ID_FILE, current_last_searched_id)
            logging.info("Stopping bot due to unexpected critical error.")
            countdown_sleep(SLEEP_AFTER_CRITICAL_ERROR_BEFORE_EXIT, "Exiting after critical error in: ")
            break


if __name__ == "__main__":
    try:
        main_interactive_loop()
    except Exception as e_top: # Catch any unexpected exit from main_interactive_loop
        logging.critical(f"Bot exited with an unhandled error at the highest level: {e_top}")
        logging.critical(traceback.format_exc())
    finally:
        logging.info("Interactive bot session ended.")
        print("\nBot session ended.")