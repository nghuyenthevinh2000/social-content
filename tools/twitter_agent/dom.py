"""X DOM identifiers, grouped by feature; interaction and safety checks live elsewhere.

Selectors can be used by Playwright locators or passed to browser JavaScript.
"""

# Posts / author / metrics
ARTICLE = 'article[data-testid="tweet"]'
AUTHOR = '[data-testid="User-Name"]'
TWEET_TEXT = '[data-testid="tweetText"]'
TIMESTAMP_LINK = 'a[href*="/status/"]'
TIMESTAMP = 'time'
QUOTE_TWEET = '[data-testid="quoteTweet"]'
REPLY_BUTTON = '[data-testid="reply"]'
RETWEET_BUTTON = '[data-testid="retweet"]'
LIKE_BUTTON = '[data-testid="like"]'
ANALYTICS_LINK = 'a[href*="/analytics"]'
AD_LABEL = 'span'
PRIMARY_COLUMN = '[data-testid="primaryColumn"]'

# Composer / attachments / submission
COMPOSER_DIALOG = '[role="dialog"]'
COMPOSER_TEXTAREA = '[data-testid="tweetTextarea_0"]'
SUBMIT_BUTTON = '[data-testid="tweetButton"]'
SUBMIT_BUTTON_INLINE = '[data-testid="tweetButtonInline"]'
FILE_INPUT = 'input[type="file"]'
ATTACHMENTS = '[data-testid="attachments"]'
ATTACHED_IMAGES = '[data-testid="attachments"] img'

# Account / login / challenges
LOGIN_BUTTON = '[data-testid="loginButton"]'
LOGIN_LINK = 'a[href="/login"]'
AUTHENTICATED_HOME = '[data-testid="AppTabBar_Home_Link"]'
ACCOUNT_SWITCHER = '[data-testid="SideNav_AccountSwitcher_Button"]'
PROFILE_LINK = '[data-testid="AppTabBar_Profile_Link"]'
CHALLENGE_CONTAINER = '[data-testid="challenge"]'
ARKOSE_IFRAME = 'iframe[src*="arkoselabs"], iframe[title*="challenge"]'
EMPTY_STATE = '[data-testid="emptyState"]'
