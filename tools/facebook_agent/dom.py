"""Facebook DOM identifiers, grouped by feature.

Each function returns a locator, not a click or a visibility/uniqueness check.
Page features take a page; composer features take the Create post dialog.
Only post_button accepts either scope (Facebook also has a Next-step dialog).
Identifiers target Facebook's English accessibility labels, not generated CSS.
"""

import re


# Account / login
def login_password_input(page):
    """Login form password field."""
    return page.locator('input[name="pass"]')


def account_restriction_dialog(page):
    """Account restriction or identity-confirmation dialog."""
    return page.get_by_role('dialog').filter(has_text=re.compile(
        r"temporarily blocked|account (?:has been )?(?:restricted|disabled)|confirm (?:your )?identity", re.I))


# Personal profile
PROFILE_HEADINGS = 'h1, h2, [role="heading"]'
PROFILE_OWNER_CONTROLS = (
    'div[role="button"][aria-label="Edit cover photo"], '
    'div[role="button"][aria-label="Profile picture actions"], '
    'div[role="button"][aria-label="Profile settings see more options"]'
)
PAGE_MANAGEMENT = re.compile(r'^(Manage Page|Switch into Page|Meta Business Suite)$', re.I)


def profile_heading(page):
    """Heading candidates used while waiting for the profile to load."""
    return profile_primary_heading(page).or_(
        page.locator(PROFILE_HEADINGS).filter(has_text=re.compile(r'\S+')))


def profile_primary_heading(page):
    """Level-one profile heading or modern name element; fallback for the profile name."""
    return page.get_by_role('heading', level=1).or_(
        page.locator('div[role="main"] span[dir="auto"] div[role="button"] span').first
    )


def profile_name(page, profile_path):
    """Profile heading containing a link to the canonical profile path."""
    return page.locator(PROFILE_HEADINGS).filter(
        has=page.locator(f'a[href*="{profile_path}"]'))


def profile_edit_control(page):
    """Edit profile button/link, or alternative own-profile controls."""
    return page.get_by_role('button', name='Edit profile', exact=True).or_(
        page.get_by_role('link', name='Edit profile', exact=True)
    ).or_(page.locator(PROFILE_OWNER_CONTROLS))


def page_management_control(page):
    """Page-only management controls."""
    return page.get_by_role('button', name=PAGE_MANAGEMENT).or_(
        page.get_by_role('link', name=PAGE_MANAGEMENT))


def switch_into_page_control(page):
    """A Page viewed without its posting identity being active."""
    return page.get_by_role('button', name='Switch into Page', exact=True).or_(
        page.get_by_role('link', name='Switch into Page', exact=True))


# Composer / identity / audience / text
COMPOSER_TRIGGER = re.compile(r"^(What's on your mind|Write something)", re.I)
AUDIENCE = re.compile(r'^(Edit privacy|Public|Friends(?: except.*)?|Only me|Custom|Specific friends)(?:\b|$)', re.I)
POST_TEXTBOX = '[role="textbox"][contenteditable="true"]'
NON_EDITABLE = ':not([contenteditable="true"]):not([contenteditable="true"] *)'


def composer_trigger(page):
    """Profile button that opens the post composer."""
    return page.get_by_role('button', name=COMPOSER_TRIGGER)


def composer_dialog(page):
    """Create post dialogs, identified by their exact heading."""
    return page.get_by_role('dialog').filter(
        has=page.get_by_role('heading', name='Create post', exact=True))


def composer_dialog_with_textbox(dialogs):
    """Disambiguate multiple Create post dialogs by a contained textbox."""
    return dialogs.filter(has=dialogs.page.locator('[role="textbox"]'))


def posting_identity(dialog, profile_name):
    """Exact author name outside editable content (never the post text)."""
    return dialog.get_by_text(profile_name, exact=True).and_(dialog.locator(NON_EDITABLE))


def audience_button(dialog):
    """Current audience / Edit privacy button."""
    return dialog.get_by_role('button', name=AUDIENCE)


def post_textbox(dialog):
    """Editable post body."""
    return dialog.locator(POST_TEXTBOX)


# Attachments
REMOVE_MEDIA = re.compile(r'^Remove (?:post )?(?:photo|image|video|attachment|gif)(?:\b|$)', re.I)
REMOVE_PHOTO = re.compile(r'^Remove (?:post )?(?:photo|image|attachment)(?:\b|$)', re.I)


def attachment_inputs(dialog):
    """All file inputs, including hidden inputs and restored attachments."""
    return dialog.locator('input[type="file"]')


def image_upload_input(dialog):
    """Image-accepting file input; normally hidden, so do not filter visibility."""
    return dialog.locator('input[type="file"][accept*="image"]')


def video_upload_input(dialog):
    """Video-accepting file input; normally hidden, so do not filter visibility."""
    return dialog.locator('input[type="file"][accept*="video"]')


def photo_video_button(dialog):
    """Button that exposes the image upload input."""
    return dialog.get_by_role('button', name=re.compile(r'^Photo/video$', re.I))


def remove_attachment_button(dialog):
    """Removal controls for any media type the composer may contain."""
    return dialog.get_by_role('button', name=REMOVE_MEDIA)


def remove_photo_button(dialog):
    """Photo removal control used as the uploaded-image preview signal."""
    return dialog.get_by_role('button', name=REMOVE_PHOTO)


def uploaded_image(dialog, filename):
    """Image preview whose alt text matches the supplied filename."""
    return dialog.locator(f'img[alt="{filename}"]')


def uploaded_video(dialog):
    """Video preview element the composer renders once a video is attached."""
    return dialog.locator('video')


# Submission / confirmation
SUCCESS = re.compile(r'^(?:Your (?:post|reel|video) (?:has been shared|was shared|has been published|is now live|is being processed|has been posted)|(?:Post|Reel|Video) (?:shared|published|posted))(?:.*)?$', re.I)


def next_button(dialog):
    """Optional Next button before the final Post step."""
    return dialog.get_by_role('button', name='Next', exact=True)


def post_button(scope):
    """Exact Post button, scoped to the composer or the next-step page."""
    return scope.get_by_role('button', name='Post', exact=True)


def submission_dialog(page, submit):
    """Dialog containing the final Post button after Next."""
    return page.get_by_role('dialog').filter(has=submit)


def post_confirmation(page):
    """Success status/alert candidates; callers check visibility and freshness."""
    return page.get_by_role('status').or_(page.get_by_role('alert')).filter(has_text=SUCCESS)


def confirmation_links(confirmation):
    """Observed links inside one fresh success status; never profile/feed links."""
    return confirmation.get_by_role('link')


# Multi-group sharing (composer "Post settings"/"Reel settings" step)
SHARE_TO_GROUPS = re.compile(r'^Share to groups', re.I)
GROUPS_PICKER_TEXT = re.compile(r'Post in up to\s+(\d+)\s+groups', re.I)


def share_to_groups_button(scope):
    """Control that opens the group picker on the composer's Post settings step."""
    return scope.get_by_role('button', name=SHARE_TO_GROUPS)


def post_settings_dialog(page):
    """Final composer step (Post settings or Reel settings) hosting group sharing."""
    return page.get_by_role('dialog').filter(has=share_to_groups_button(page))


def groups_picker_dialog(page):
    """Dialog listing the groups a post can also be shared to."""
    return page.get_by_role('dialog').filter(has_text=GROUPS_PICKER_TEXT)


def groups_done_button(dialog):
    """Confirms the group selection and returns to Post settings."""
    return dialog.get_by_role('button', name='Done', exact=True)


# Direct messages
MESSAGE_BUTTON = re.compile(r'^(?:Message|Send message)$', re.I)
MESSAGE_TEXTBOX = '[role="textbox"][contenteditable="true"]'
SEND_BUTTON = re.compile(r'^(?:Send|Press Enter to send)$', re.I)
CANNOT_MESSAGE = re.compile(
    r"(?:can't|cannot|isn't able to|unable to) (?:be )?(?:message|messaged)|"
    r"this person isn't available|messaging (?:isn't|is not) available", re.I)


def message_button(page):
    """Profile control that opens the direct-message composer."""
    return page.get_by_role('button', name=MESSAGE_BUTTON).or_(
        page.get_by_role('link', name=MESSAGE_BUTTON))


def message_dialog(page):
    """Direct-message dialog, identified by containing a message input."""
    return page.get_by_role('dialog').filter(has=page.locator(MESSAGE_TEXTBOX))


def message_textbox(dialog):
    """Editable message input inside the direct-message dialog."""
    return dialog.locator(MESSAGE_TEXTBOX)


def send_button(dialog):
    """Send control for the direct-message dialog."""
    return dialog.get_by_role('button', name=SEND_BUTTON)


def sent_bubble(dialog, text):
    """Sent message bubble with the exact text, excluding the editable composer."""
    return dialog.get_by_text(text, exact=True).and_(dialog.locator(NON_EDITABLE))


def cannot_message_notice(page):
    """Notice that this recipient cannot receive a direct message."""
    return page.get_by_text(CANNOT_MESSAGE)
