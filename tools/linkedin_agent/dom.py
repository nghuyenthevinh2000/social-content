"""LinkedIn DOM identifiers, grouped by feature.

Constants can be used by Playwright locators or browser-side safety checks.
Locator helpers only identify controls; callers handle actions and readiness.
Identifiers target English controls and both legacy and native-dialog layouts.
"""

import re


# Account / login
LOGIN_FORM = 'form[action*="login"], input[name="session_password"], input#password'
CHECKPOINT_FORM = 'form[action*="/checkpoint/"], #captcha-internal'
CHALLENGE_FRAME = 'iframe[src*="captcha"], iframe[src*="arkoselabs"], iframe[title*="captcha" i], iframe[title*="challenge" i]'


# Feed / composer
# Keep legacy navigation scoped; modern feed navigation uses a current Home button.
AUTHENTICATED_HOME = (
    '#global-nav a[href="/feed/"], #global-nav a[href="https://www.linkedin.com/feed/"], '
    'nav button:has(svg[id^="home-active"]), '
    'nav button[aria-current="true"]:is([aria-label="Home"], [aria-label^="Home, "])'
    ':is(:text-is("Home"), :has(:text-is("Home")))'
)
# Match the actionable container, not its noninteractive accessible-label child.
START_POST = (
    'div[role="button"][tabindex="0"]:has(#draft-text-replaceable-component), '
    'button.share-box-feed-entry__trigger, '
    'button:has-text("Start a post"), '
    'div[role="button"][tabindex="0"]:has(div[aria-label="Start a post"])'
)
HYDRATED_BODY = 'body[data-rehydrated="true"]'
MODERN_COMPOSER = 'dialog[open][data-testid="dialog"]:has([data-sdui-screen="com.linkedin.sdui.flagshipnav.sharing.ShareCompose"])'
COMPOSER = '[role="dialog"]:has(.share-creation-state__text-editor), [role="dialog"][aria-label="Create a post"], ' + MODERN_COMPOSER
EDITOR = '.share-creation-state__text-editor [contenteditable="true"], [contenteditable="true"][role="textbox"]'


# Personal author / picker
OWN_PROFILE = '#shareboxProfilePictureComponentRef a[href]'
AUTHOR_PICKER = '[data-testid="lazy-column"][data-component-type="LazyColumn"]:has(input[type="radio"]), [data-testid="lazy-column"][data-component-type="LazyColumn"]:has(p:text-is("Post as"))'
MODERN_AUTHOR = 'div[role="button"][tabindex="0"][aria-expanded]:has(svg#caret-small):not(:has(svg#visibility-small)):not(:has(svg#comment-small))'
AUTHOR = '.share-creation-state__member-info a[href], .share-creation-state__profile-info a[href]'
AUTHOR_LABEL = 'div[aria-label]'
NAMED_PROFILE = 'a[href]:has(figure svg#person-accent-4[aria-label])'
PERSONAL_ICON = 'svg#person-accent-4'
PERSONAL_FIGURE_ICON = 'figure ' + PERSONAL_ICON
PERSONAL_AVATAR = 'figure:has(' + PERSONAL_ICON + ')'
PERSONAL_AVATAR_IMAGE = PERSONAL_AVATAR + ' img'
COMPANY_ICON = 'svg#company-accent-4'
SELECTED_AUTHOR = 'input[type="radio"]:checked'
FIGURE = 'figure'
FIGURE_IMAGE = 'figure img'
AUTHOR_NAMES = 'p'
RADIO_LABEL = 'label'


# Attachments
ADD_MEDIA = 'button[aria-label="Add media"], button[aria-label="Add a photo"], button[aria-label="Add photos"], button[aria-label="Add an image"], button[aria-label="Media"][aria-haspopup="dialog"], button:has(svg#image-medium)'
MEDIA_DIALOG = (
    '[role="dialog"]:not(:has(.share-creation-state__text-editor)):not([aria-label="Create a post"])'
    ':is(:has(input[type="file"]), [aria-label="Media editor"], [aria-label="Edit your photo"], [aria-label="Edit your images"])'
    ', dialog[open][data-testid="dialog"]:has(header h2:text-is("Editor")), dialog[open][data-testid="dialog"]:has(header h2)'
)
FILE_INPUT = 'input[type="file"]'
MODERN_THUMBNAIL = 'img[alt^="image "]'
MODERN_ATTACHMENT = 'figure:has(svg#image-medium):not(:has(svg#person-accent-4)) img'
IMAGE_PREVIEW = 'img.share-images__image, img.image-sharing-preview__image, .share-creation-state__image img, ' + MODERN_THUMBNAIL + ', ' + MODERN_ATTACHMENT
MEDIA_IMAGE_PREVIEW = IMAGE_PREVIEW + ', img[alt="Image Preview"]'
UPLOAD_PROGRESS = '[role="progressbar"], [aria-busy="true"], .artdeco-loader, .image-sharing-preview__progress-bar'
UPLOAD_ERROR = '[role="alert"], .artdeco-inline-feedback--error, .image-sharing-preview__error'
AWAITING_FILE_LOADER = '[data-testid="add-media-drop-zone"] button[aria-busy="true"][disabled]'


# Submission / confirmation
BUTTON = 'button'
POST_LABEL = 'Post'
MEDIA_ADVANCE = re.compile(r'^(Next|Done)$')
NOTIFICATION = '.artdeco-toast-item, [role="status"], [role="alert"]'
NOTIFICATION_MESSAGE = '.artdeco-toast-item__message'
NOTIFICATION_LINK = 'a[href]'
SUCCESS = re.compile(r'^(?:Post successful[.!]?|Your post (?:was (?:successfully )?posted|is now live|has been published)[.!]?)(?:\s|$)', re.IGNORECASE)


def media_advance_button(dialog):
    """Next or Done control inside the active media dialog."""
    return dialog.get_by_role('button', name=MEDIA_ADVANCE)


def post_button(composer):
    """Exact Post control inside the personal composer."""
    return composer.get_by_role('button', name=POST_LABEL, exact=True)
