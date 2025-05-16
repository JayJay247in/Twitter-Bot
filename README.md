# Interactive Twitter Engagement Bot (API v2)

This Python-based bot allows users to interactively configure and run automated engagements (retweets, likes, follows) on Twitter based on a specified search query. It's designed with the Twitter API v2 Free Tier limitations in mind, incorporating robust rate limit handling, action cooldowns, and persistence.

## Features

*   **Interactive Setup:** Prompts the user for all necessary configurations at runtime:
    *   Twitter API Credentials (API Key/Secret, Access Token/Secret, Bearer Token) - input is hidden.
    *   Search Query (e.g., hashtags, keywords, user mentions).
    *   Maximum results to fetch per search batch.
    *   Actions to perform (Retweet, Like, Follow - can be toggled individually).
    *   User blocklist (usernames whose tweets will be ignored).
    *   Negative keywords (phrases that, if present in a tweet, will cause it to be skipped).
*   **Twitter API v2:** Utilizes the modern Twitter API v2 via the `tweepy` library.
*   **Rate Limit Aware:**
    *   Handles Twitter API rate limits gracefully, especially the strict search (1 req/15 min) and action (like/follow/retweet) limits on the Free Tier.
    *   Implements configurable cooldown periods for each action type.
*   **Intelligent Interaction:**
    *   Avoids interacting with the bot's own tweets.
    *   Can target original tweets when encountering retweets (for likes and follows).
    *   Skips retweeting content that is already a retweet found in search results.
*   **Persistence:**
    *   Remembers the `last_searched_id` to fetch newer tweets efficiently across sessions.
    *   Keeps track of tweets already liked and retweeted, and users already followed, to prevent redundant actions (data stored in local text files).
*   **Filtering:**
    *   Filters tweets based on a user-defined blocklist of usernames.
    *   Filters tweets based on user-defined negative keywords.
    *   Includes a configurable language filter (defaulted to English).
*   **Robust Logging:**
    *   Detailed logging of all actions, decisions, errors, and cooldowns to both the console and a rotating log file (`twitter_interactive_bot.log`).
    *   Configurable log level.
*   **Live Countdown:** Displays a live countdown on the console for sleep periods, providing better user feedback.
*   **Graceful Exit:** Handles `KeyboardInterrupt` (Ctrl+C) to stop the bot and attempt to save its last state.

## Prerequisites

*   Python 3.7+
*   A Twitter Developer Account with an App created that has:
    *   Access to the Twitter API v2.
    *   Generated API Key & Secret, Access Token & Secret, and a Bearer Token.
    *   App permissions set to "Read and Write" (or "Read, Write, and Direct Messages") in the User authentication settings.
    *   User authentication settings configured with a Callback URI (e.g., `http://127.0.0.1`) and Website URL.

## Setup

1.  **Clone the Repository (or create the files):**
    ```bash
    # If you have a git repo:
    # git clone https://github.com/JayJay247in/Twitter-Bot.git
    # cd Twitter-Bot
    ```
    Otherwise, ensure `twitter_interactive_bot.py` and `config.py` (though `config.py` is mostly for defaults/log settings now) are in the same directory. The `credentials.py` file is **not** used by this interactive version for API keys, as they are input by the user.

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    The primary dependency is `tweepy`.
    ```bash
    pip install tweepy
    ```

## Configuration (`config.py`)

While most operational parameters are requested interactively, the `config.py` file still holds some default values, file paths for persistence, and logging settings. You can review and adjust these defaults if needed.

Key settings you might review in `config.py`:
*   `SEARCH_INTERVAL_SUCCESS`, `SEARCH_INTERVAL_NO_RESULTS`
*   `LIKE_COOLDOWN_SECONDS`, `FOLLOW_COOLDOWN_SECONDS`, `RETWEET_COOLDOWN_SECONDS`
*   `SLEEP_BETWEEN_BATCH_ACTIONS`, `SHORT_SLEEP_IF_NO_ACTIONS`
*   Default `USER_BLOCKLIST_USERNAMES`, `NEGATIVE_KEYWORDS_IN_TEXT`, `TARGET_LANGUAGES`
*   Persistence filenames (e.g., `LIKED_TWEET_IDS_FILE`)
*   Logging settings (`LOG_FILE`, `LOG_LEVEL`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`)

**Note on Persistence Files:**
The bot creates text files (e.g., `liked_tweet_ids_interactive.txt`, `last_searched_id_interactive.txt`) in the same directory where it runs to store state. These files are global for all interactive sessions unless you modify the script to create user/query-specific filenames.

## Running the Bot

1.  Ensure your virtual environment is activated.
2.  Run the script from your terminal:
    ```bash
    python twitter_interactive_bot.py
    ```
3.  The bot will then prompt you to enter:
    *   Your Twitter API credentials (input will be hidden).
    *   Your desired search query and max results per batch.
    *   Your preferences for enabling Retweet, Like, and Follow actions.
    *   Any usernames for the blocklist.
    *   Any negative keywords for filtering tweets.

4.  Once all inputs are provided, the bot will authenticate and start its operation based on your configuration.
5.  Monitor the console output and the `twitter_interactive_bot.log` file for activity and any potential issues.
6.  To stop the bot, press `Ctrl+C`. It will attempt a graceful shutdown and save its last searched tweet ID.

## How It Works (Brief Overview)

1.  **Input & Initialization:** Gathers all parameters from the user and initializes the Tweepy client.
2.  **Search Loop:** Periodically searches Twitter for recent tweets matching the user's query, using `since_id` for pagination.
3.  **Filtering:** Each found tweet is passed through filters (own tweet, blocklist, negative keywords, language).
4.  **Action Logic:** If a tweet passes filters:
    *   It determines if the tweet is an RT and identifies the original tweet/author if applicable.
    *   For each enabled action (Retweet, Like, Follow):
        *   Checks if the action was already performed on the target (using persistence files).
        *   Checks if the action-specific cooldown period has passed.
        *   If all checks pass, it attempts the API call.
        *   Handles API errors (including rate limits) and updates persistence/cooldown timestamps.
5.  **Pacing:** Uses various sleep intervals to manage API call frequency and respect rate limits.
    *   Short sleep between processing individual tweets in a batch.
    *   Longer sleep between entire search attempts.
    *   Specific cooldowns after hitting rate limits for search or actions.

## Important Considerations for Free Tier

*   **Search Limit:** 1 request / 15 minutes. The bot adheres to this by sleeping for at least 15 minutes after a search attempt that used its quota.
*   **Action Limits (Like, Follow, Retweet):** These are very strict (often 1 per 15 minutes, or very low daily caps). The bot uses long cooldown periods for these actions. You will likely see many "Skipping action: Still in cooldown period" messages if actions are enabled. This is normal behavior to avoid account suspension.
*   **It's recommended to be conservative with enabling Like and Follow actions on the Free Tier.** Retweeting is generally a bit more lenient but still has limits.

## Troubleshooting

*   **`401 Unauthorized` on startup:** Double-check all 5 credentials (Bearer Token, API Key/Secret, Access Token/Secret) are copied correctly from your Twitter Developer App that is configured for API v2 and has "Read and Write" permissions. Ensure User Authentication Settings (Callback URI, etc.) are set up in the Developer Portal for that app. Regenerate Access Token/Secret if you changed app permissions.
*   **`429 Too Many Requests`:** The bot is hitting a rate limit. It should handle this by sleeping. If it happens too often for actions like "Like" or "Follow", consider increasing their respective `*_COOLDOWN_SECONDS` in `config.py` or disabling those actions.
*   Check `twitter_interactive_bot.log` for detailed error messages and operational flow.

## Contributing

Feel free to fork this project, suggest improvements, or submit pull requests if you have enhancements!

## License

(Optional: Add a license if you plan to share this publicly, e.g., MIT License)