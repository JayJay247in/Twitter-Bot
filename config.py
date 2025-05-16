# config.py

# --- Search Configuration ---
QUERY = '#alxafrica' # Your primary search query
# How often to attempt a new search if the previous one found tweets (seconds)
# Must be >= 905 for Free Tier search (1 req / 15 mins)
SEARCH_INTERVAL_SUCCESS = 905  # 15 minutes + 5s buffer
# How often to attempt a new search if the previous one found NO tweets (seconds)
SEARCH_INTERVAL_NO_RESULTS = 300 # 5 minutes

# --- Action Configuration ---
PERFORM_RETWEET = True
PERFORM_LIKE = True    # Be very cautious with this on Free Tier
PERFORM_FOLLOW = True  # Be very cautious with this on Free Tier

# Cooldown in seconds before ATTEMPTING the same action type again
# (after a successful action or hitting a rate limit for that action type)
# Free Tier limits are very strict (often ~1 per 15 mins or low daily cap for like/follow)
LIKE_COOLDOWN_SECONDS = 15 * 60 + 15   # 915s (~15 minutes)
FOLLOW_COOLDOWN_SECONDS = 15 * 60 + 20 # 920s (~15 minutes)
RETWEET_COOLDOWN_SECONDS = 15 * 60 + 10 # 910s (~15 minutes - adjust based on observation)

# Sleep between processing individual tweets found in ONE search batch
SLEEP_BETWEEN_BATCH_ACTIONS = 60 # seconds (if an API-calling action was ATTEMPTED)
SHORT_SLEEP_IF_NO_ACTIONS = 10   # seconds (if only filtering/skipping occurred for a tweet)

# --- User Filtering ---
# Bot will not interact with tweets from these users (case-insensitive usernames)
USER_BLOCKLIST_USERNAMES = {"spamuser1", "ignorethisuser", "anotherbot"}
# Bot will not interact with its own tweets (this is auto-detected)

# --- Content Filtering ---
# Bot will skip tweets containing any of these case-insensitive phrases in their text
NEGATIVE_KEYWORDS_IN_TEXT = [
    "#ignorethis", "buy now", "limited time offer", "crypto scam",
    "adult content", "click here for free" # Add more as needed
]
# Optional: Filter by language (e.g., ["en", "es"]). Leave empty to not filter.
# Requires 'lang' in tweet_fields.
TARGET_LANGUAGES = ["en"]


# --- Persistence Files ---
LIKED_TWEET_IDS_FILE = "liked_tweet_ids.txt"
RETWEETED_TWEET_IDS_FILE = "retweeted_tweet_ids.txt"
FOLLOWED_USER_IDS_FILE = "followed_user_ids.txt"
LAST_SEARCHED_ID_FILE = "last_searched_id.txt"

# --- Logging ---
LOG_FILE = "twitter_bot_activity.log" # Renamed for clarity
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_MAX_BYTES = 5 * 1024 * 1024 # 5MB
LOG_BACKUP_COUNT = 3            # Number of backup log files

# --- General Error Handling ---
SLEEP_AFTER_GENERIC_API_ERROR = 60 # seconds
SLEEP_AFTER_CRITICAL_ERROR_BEFORE_EXIT = 5 # seconds (just to ensure logs are flushed)