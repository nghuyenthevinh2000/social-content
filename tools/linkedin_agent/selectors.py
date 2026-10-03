"""Centralized LinkedIn selectors with fail-closed readiness and block checks."""

from urllib.parse import urlsplit

from .models import AgentError

# Keep legacy navigation scoped; modern feed navigation uses a current Home button.
AUTHENTICATED_HOME = (
    '#global-nav a[href="/feed/"], #global-nav a[href="https://www.linkedin.com/feed/"], '
    'nav button[aria-current="true"]:is([aria-label="Home"], [aria-label^="Home, "])'
    ':is(:text-is("Home"), :has(:text-is("Home")))'
)
# Match the actionable container, not its noninteractive accessible-label child.
START_POST = (
    'button:has-text("Start a post"), button.share-box-feed-entry__trigger, '
    'div[role="button"][tabindex="0"]:has(div[aria-label="Start a post"])'
)
MODERN_COMPOSER = 'dialog[open][data-testid="dialog"]:has([data-sdui-screen="com.linkedin.sdui.flagshipnav.sharing.ShareCompose"])'
COMPOSER = '[role="dialog"]:has(.share-creation-state__text-editor), [role="dialog"][aria-label="Create a post"], ' + MODERN_COMPOSER
OWN_PROFILE = '#shareboxProfilePictureComponentRef a[href]'
AUTHOR_PICKER = '[data-testid="lazy-column"][data-component-type="LazyColumn"]:has(p:text-is("Post as"))'
MODERN_AUTHOR = 'div[role="button"][tabindex="0"][aria-expanded]:has(svg#caret-small):not(:has(svg#visibility-small)):not(:has(svg#comment-small))'
AUTHOR = '.share-creation-state__member-info a[href], .share-creation-state__profile-info a[href]'
EDITOR = '.share-creation-state__text-editor [contenteditable="true"], [contenteditable="true"][role="textbox"]'
ADD_MEDIA = 'button[aria-label="Add media"], button[aria-label="Add a photo"], button[aria-label="Add photos"], button[aria-label="Add an image"], button[aria-label="Media"][aria-haspopup="dialog"]'
MEDIA_DIALOG = (
    '[role="dialog"]:not(:has(.share-creation-state__text-editor)):not([aria-label="Create a post"])'
    ':is(:has(input[type="file"]), [aria-label="Media editor"], [aria-label="Edit your photo"], [aria-label="Edit your images"])'
    ', dialog[open][data-testid="dialog"]:has(header h2:text-is("Editor"))'
)
FILE_INPUT = 'input[type="file"]'
MODERN_THUMBNAIL = 'img[alt^="image "]'
MODERN_ATTACHMENT = 'figure:has(svg#image-medium):not(:has(svg#person-accent-4)) img'
IMAGE_PREVIEW = 'img.share-images__image, img.image-sharing-preview__image, .share-creation-state__image img, ' + MODERN_THUMBNAIL + ', ' + MODERN_ATTACHMENT
UPLOAD_PROGRESS = '[role="progressbar"], [aria-busy="true"], .artdeco-loader, .image-sharing-preview__progress-bar'
UPLOAD_ERROR = '[role="alert"], .artdeco-inline-feedback--error, .image-sharing-preview__error'
NOTIFICATION = '.artdeco-toast-item, [role="status"], [role="alert"]'
LOGIN_FORM = 'form[action*="login"], input[name="session_password"], input#password'
CHECKPOINT_FORM = 'form[action*="/checkpoint/"], #captcha-internal'
CHALLENGE_FRAME = 'iframe[src*="captcha"], iframe[src*="arkoselabs"], iframe[title*="captcha" i], iframe[title*="challenge" i]'


def detect_block(page):
    """Raise structured errors for login and checkpoints; never bypass either."""
    path = urlsplit(page.url).path.lower()
    if (path.startswith('/checkpoint/') or path == '/checkpoint'
            or page.locator(CHECKPOINT_FORM).count() > 0
            or any(frame.is_visible() for frame in page.locator(CHALLENGE_FRAME).all())):
        raise AgentError(
            'browser_challenge', 'LinkedIn checkpoint detected. Complete it manually in Chrome.',
            human_action_required=True,
        )
    login = page.locator(LOGIN_FORM)
    if (path in ('/login', '/uas/login', '/authwall')
            or any(login.nth(index).is_visible() for index in range(login.count()))):
        raise AgentError(
            'not_authenticated', 'Log into LinkedIn manually in the shared Chrome profile.',
            human_action_required=True,
        )


def unique_locator(page, selector: str):
    """Return exactly one match; never silently select the first ambiguous control."""
    locator = page.locator(selector)
    count = locator.count()
    if count > 1:
        raise AgentError('ambiguous_selector', 'Multiple LinkedIn controls matched; inspect the page manually.')
    if count == 0:
        raise AgentError('dom_timeout', 'Expected LinkedIn control was not found.')
    return locator


def wait_for_selector_or_block(page, selector: str, timeout_ms: int = 15000):
    """Wait for one visible control, checking blocks before and after the wait."""
    detect_block(page)
    if page.locator(selector).count() > 1:
        return unique_locator(page, selector)
    try:
        page.locator(selector).wait_for(state='visible', timeout=timeout_ms)
    except Exception as exc:
        detect_block(page)
        if page.locator(selector).count() > 1:
            return unique_locator(page, selector)
        raise AgentError('dom_timeout', 'Timed out waiting for LinkedIn feed controls.') from exc
    detect_block(page)
    return unique_locator(page, selector)
