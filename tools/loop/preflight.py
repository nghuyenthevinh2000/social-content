"""Offline content gates and hash-bound human decisions; never publishes.

Policy lives in loop/config.json. Artifact paths in content.json are relative
to posts/<id>/; brand/policy paths are relative to the project. Stdlib only.
"""

from datetime import date
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from tools.loop import storage


STAGES = ('research', 'draft', 'visual', 'publish')
CHANNEL_FILES = {
    'facebook_page': ('facebook*.md',),
    'facebook_profile': ('facebook*.md',),
    'linkedin': ('linkedin*.md',),
    'twitter': ('twitter*.md', 'x-post*.md'),
}


class GateError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def require(condition, code, detail):
    if not condition:
        raise GateError(code, detail)


def read_json(path):
    require(path.is_file(), 'missing_artifact', f'Missing {path.name}: {path}')
    value = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(value, dict), 'invalid_artifact', f'{path.name} must be a JSON object.')
    return value


def text_value(value):
    return (isinstance(value, str) and bool(value.strip())
            and not re.search(r'\b(TODO|TBD|PLACEHOLDER)\b|<.*?>|\[(?:insert|replace|fill)[^\]]*\]', value, re.I))


def post_directory(root, post):
    require(type(post) is int and post > 0, 'invalid_post', 'Post must be a positive integer.')
    return storage.project_file(root, f'posts/{post}')


def _remember(root, files, path):
    path = path.resolve()
    require(path.is_relative_to(root), 'path_escape', 'Artifact must stay inside the project.')
    require(path.is_file(), 'missing_artifact', f'Missing {path}')
    files[str(path.relative_to(root))] = storage.sha256_file(path)


def _revision(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def _base(root, post):
    config = storage.load_project(root)
    policy = config.get('content_policy')
    require(isinstance(policy, dict) and policy.get('schema_version') == 1,
            'missing_policy', 'Configure content_policy.schema_version = 1 before content preflight.')
    for key in ('required_cta', 'forbidden_artifacts'):
        values = policy.get(key, [])
        require(isinstance(values, list) and all(isinstance(value, str) and value.strip() for value in values),
                'invalid_policy', f'{key} must be a list of nonempty strings.')
    require(type(policy.get('require_visual', False)) is bool, 'invalid_policy', 'require_visual must be a boolean.')
    if 'research' in policy:
        rules = policy['research']
        require(isinstance(rules, dict) and bool(rules), 'invalid_policy', 'research must contain evidence requirements.')
        for key in ('min_primary_statutes', 'min_case_studies'):
            require(type(rules.get(key, 0)) is int and rules.get(key, 0) >= 0,
                    'invalid_policy', f'{key} must be a nonnegative integer.')
        hosts = rules.get('primary_hosts', [])
        require(isinstance(hosts, list) and all(isinstance(host, str) and re.fullmatch(r'[a-z0-9.-]+\.[a-z]+', host)
                                               for host in hosts), 'invalid_policy', 'primary_hosts must contain bare lowercase hostnames.')
    channels = config.get('allowed_channels')
    require(isinstance(channels, list) and bool(channels)
            and all(channel in CHANNEL_FILES for channel in channels),
            'invalid_policy', 'allowed_channels must explicitly list supported channels.')
    directory = post_directory(root, post)
    hypotheses = storage.load_hypotheses(root, config)
    if config.get('hypotheses_file'):
        active_item = next((item for item in hypotheses.get('hypotheses', []) if item.get('post') == post), None)
        require(active_item is not None, 'unknown_post', 'Post is not in the configured hypotheses file.')
        hook_obj = active_item.get('hook') if active_item else None
        if isinstance(hook_obj, dict) and hook_obj.get('type'):
            from tools.loop import validate
            db_path = validate.find_database(root)
            if db_path and db_path.is_file():
                valid_ids, slug_to_id, _ = validate.load_canonical_hooks(db_path)
                valid, err = validate.check_single_hook(hook_obj['type'], valid_ids, slug_to_id)
                require(valid, 'invalid_hook_type', err)
    files = {}
    for relative in ('loop/config.json', 'AGENTS.md', config.get('hypotheses_file'),
                     config.get('brand_manifest'), policy.get('guidelines_file'), policy.get('tokens_file')):
        if relative:
            _remember(root, files, storage.project_file(root, relative))
    # Scope checks to the selected active post; historical drafts are untouched.
    for path in directory.rglob('*'):
        if not path.is_file():
            continue
        forbidden = any(fnmatch.fnmatch(path.name, pattern)
                        for pattern in policy.get('forbidden_artifacts', []))
        for channel, patterns in CHANNEL_FILES.items():
            if channel not in channels and not any(
                    set(patterns) & set(CHANNEL_FILES[allowed]) for allowed in channels):
                forbidden |= any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
        require(not forbidden, 'channel_artifact', f'Unauthorized channel artifact: {path.name}')
    return config, policy, directory, files


def _check_date(value, label):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise GateError('research_date', f'{label} needs an ISO YYYY-MM-DD date.') from None
    return parsed


def _research(root, directory, policy, files):
    rules = policy.get('research')
    if not rules:
        return
    dossier = storage.project_file(directory, 'research.md')
    _remember(root, files, dossier)
    require(text_value(dossier.read_text(encoding='utf-8')), 'research_empty',
            'research.md is empty or contains placeholders.')
    evidence_path = storage.project_file(directory, 'research.json')
    evidence = read_json(evidence_path)
    _remember(root, files, evidence_path)
    require(evidence.get('schema_version') == 1, 'research_schema', 'research.json needs schema_version 1.')
    sources = evidence.get('sources')
    require(isinstance(sources, list) and bool(sources), 'research_sources', 'Research needs source records.')
    ids, urls, counts = set(), set(), {'primary_statute': 0, 'case_study': 0}
    for source in sources:
        require(isinstance(source, dict), 'research_source', 'Each source must be an object.')
        require(all(text_value(source.get(key)) for key in
                    ('id', 'title', 'url', 'jurisdiction', 'analysis')), 'research_source',
                'Each source needs id, title, URL, jurisdiction and substantive analysis.')
        kind = source.get('type')
        require(kind in counts, 'research_source', 'Source type must be primary_statute or case_study.')
        parsed = urlparse(source['url'])
        require(parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username,
                'research_url', 'Source URLs must be absolute HTTPS URLs without credentials.')
        require(source['id'] not in ids and source['url'].rstrip('/') not in urls,
                'research_duplicate', 'Duplicate source IDs or URLs do not count as independent evidence.')
        ids.add(source['id'])
        urls.add(source['url'].rstrip('/'))
        checked = _check_date(source.get('checked_at'), 'checked_at')
        require(checked <= storage.now().date(), 'research_date', 'checked_at cannot be in the future.')
        if kind == 'primary_statute':
            hosts = rules.get('primary_hosts', [])
            require(bool(hosts) and any(parsed.hostname == host or parsed.hostname.endswith('.' + host)
                                       for host in hosts), 'research_primary_host',
                    'Primary statutes must link to a configured official source host.')
            provisions = source.get('provisions')
            require(isinstance(provisions, list) and bool(provisions) and all(map(text_value, provisions)),
                    'research_provisions', 'Statutes need exact provisions, not just document titles.')
            effective = _check_date(source.get('effective_date'), 'effective_date')
            require(effective <= checked, 'research_date', 'Future/not-yet-effective law cannot support current-law claims.')
        counts[kind] += 1
    require(counts['primary_statute'] >= rules.get('min_primary_statutes', 0)
            and counts['case_study'] >= rules.get('min_case_studies', 0), 'research_count',
            'Research does not meet the configured primary-statute / case-study minimums.')
    claims = evidence.get('claims')
    require(isinstance(claims, list) and bool(claims), 'research_claims', 'Add claim-to-source mappings.')
    for claim in claims:
        require(isinstance(claim, dict) and text_value(claim.get('claim'))
                and text_value(claim.get('limitations')), 'research_claims',
                'Each mapped claim needs its wording and jurisdiction/applicability limitations.')
        refs = claim.get('source_ids')
        require(isinstance(refs, list) and bool(refs) and all(ref in ids for ref in refs),
                'research_claims', 'Each claim must reference existing source IDs.')


def _receipt(path, fingerprint, kind):
    receipt = read_json(path)
    require(receipt.get('schema_version') == 1 and receipt.get('approved') is True and text_value(receipt.get('reviewer'))
            and receipt.get('kind') == kind and receipt.get('fingerprint') == fingerprint,
            'stale_approval', f'{kind} is absent, invalid or stale; request a new explicit human decision.')
    stamp = storage.timestamp(receipt.get('approved_at'))
    require(stamp is not None and stamp <= storage.now(), 'invalid_approval', 'Approval needs a valid past timestamp.')
    return receipt


def _content(root, directory, config, policy, files):
    path = storage.project_file(directory, 'content.json')
    manifest = read_json(path)
    require(manifest.get('schema_version') == 1, 'content_schema', 'content.json needs schema_version 1.')
    require(manifest.get('channel') in config['allowed_channels'], 'channel', 'Content channel is not allowed.')
    _remember(root, files, path)
    copy = storage.project_file(directory, manifest.get('copy'))
    _remember(root, files, copy)
    # Terminal newlines belong to the text file, not the visible post. Keep all
    # other whitespace exact; the approval still fingerprints the entire file.
    text = copy.read_text(encoding='utf-8').rstrip('\n')
    require(text_value(text), 'copy_empty', 'Copy must be nonempty and free of placeholders.')
    require(all(cta in text for cta in policy.get('required_cta', [])), 'copy_cta',
            'Copy is missing a configured phone/email CTA.')
    groups = manifest.get('groups', [])
    require(isinstance(groups, list) and len(groups) <= 9 and all(map(text_value, groups))
            and len(set(groups)) == len(groups), 'content_groups', 'groups must be unique nonempty names (max 9).')
    return manifest, text


def _svg(path, tokens):
    """Fail closed on a small SVG subset; unsupported CSS needs a reviewed conversion.

    ponytail: static SVG validation is not a renderer. Hash-bound visual approval
    must inspect the PNG and confirm it matches this source, including fonts.
    """
    raw = path.read_text(encoding='utf-8')
    require('<!DOCTYPE' not in raw.upper() and '<!ENTITY' not in raw.upper(), 'visual_svg', 'SVG entities are unsupported.')
    svg = ET.fromstring(raw)
    require(svg.tag == '{http://www.w3.org/2000/svg}svg', 'visual_svg', 'Expected a namespaced SVG document.')
    box = [float(value) for value in svg.get('viewBox', '').split()]
    require(len(box) == 4 and box[:2] == [0, 0] and all(value > 0 for value in box[2:]),
            'visual_dimensions', 'SVG needs a positive viewBox starting at 0 0.')
    allowed = {color.upper() for color in tokens['colors'].values()}
    require(all(re.fullmatch(r'#[0-9A-F]{6}', color) for color in allowed), 'visual_tokens', 'Tokens need six-digit hex colors.')
    fonts = tokens['fonts']
    require(isinstance(fonts, list) and bool(fonts) and all(map(text_value, fonts)),
            'visual_tokens', 'Tokens need approved primary font names.')
    require(svg.get('opacity', '1') == '1', 'visual_canvas', 'SVG root must be opaque.')
    safe_tags = {'svg', 'g', 'defs', 'rect', 'text', 'tspan', 'line', 'path', 'circle', 'ellipse',
                 'polyline', 'polygon', 'title', 'desc'}
    def visit(node, inherited_font=None):
        tag = node.tag.rsplit('}', 1)[-1]
        require(tag in safe_tags, 'visual_svg', f'Unsupported SVG element: {tag}; CSS, filters and embedded media are not accepted.')
        for key, value in node.attrib.items():
            require(key not in ('style', 'class', 'filter', 'clip-path', 'mask') and not key.lower().startswith('on')
                    and 'href' not in key and 'url(' not in value.lower(),
                    'visual_svg', f'Unsupported SVG attribute: {key}')
            if key in ('fill', 'stroke', 'color'):
                require(value.upper() in allowed or value == 'none', 'visual_palette', f'Off-brand paint: {value}')
        font = node.get('font-family', inherited_font)
        if tag in ('text', 'tspan'):
            primary = (font or '').split(',')[0].strip(" '\"")
            require(primary in fonts, 'visual_font', f'Use a configured primary font, not {primary!r}.')
        for child in node:
            visit(child, font)
    visit(svg)
    visible = [node for node in svg if node.tag.rsplit('}', 1)[-1] not in ('defs', 'title', 'desc')]
    require(bool(visible), 'visual_canvas', 'SVG needs an explicit paper canvas.')
    canvas = visible[0]
    require(canvas.tag.endswith('}rect') and float(canvas.get('x', 0)) == 0 and float(canvas.get('y', 0)) == 0
            and float(canvas.get('width', 0)) == box[2] and float(canvas.get('height', 0)) == box[3]
            and canvas.get('fill', '').upper() == tokens['colors']['canvas'].upper()
            and not canvas.get('transform') and not svg.get('transform')
            and canvas.get('opacity', '1') == '1' and canvas.get('fill-opacity', '1') == '1',
            'visual_canvas', 'First drawable must be an opaque full-viewBox rect using the canvas token.')
    # Do not let approved ink/accent colors replace the paper canvas.
    for node in svg.iter():
        if node is canvas or not node.tag.endswith('}rect'):
            continue
        if float(node.get('width', 0)) >= box[2] and float(node.get('height', 0)) >= box[3]:
            require(node.get('fill', 'none') in ('none', tokens['colors']['canvas']),
                    'visual_canvas', 'A full-canvas overlay must not replace the paper background.')
    return box[2:]


def _visual(root, directory, policy, manifest, files):
    visual = manifest.get('visual')
    require(bool(visual) or not policy.get('require_visual'), 'visual_missing', 'A visual source and rendered PNG are required.')
    if not visual:
        return None
    require(isinstance(visual, dict) and policy.get('tokens_file'), 'visual_tokens', 'Visual validation needs tokens_file.')
    tokens = read_json(storage.project_file(root, policy['tokens_file']))
    source = storage.project_file(directory, visual.get('source'))
    image = storage.project_file(directory, visual.get('image'))
    _remember(root, files, source)
    require(source.suffix.lower() == '.svg', 'visual_svg', 'Validated visual source must be SVG.')
    width, height = _svg(source, tokens)
    _remember(root, files, image)
    with image.open('rb') as stream:
        header = stream.read(24)
    require(len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR',
            'visual_png', 'Rendered image must be PNG with an IHDR header.')
    rendered = struct.unpack('>II', header[16:24])
    scale = tokens.get('render_scale', 2)
    require(type(scale) is int and 1 <= scale <= 4, 'visual_tokens', 'render_scale must be an integer from 1 to 4.')
    require(rendered == (width * scale, height * scale), 'visual_dimensions',
            f'PNG dimensions must be {width * scale:g} x {height * scale:g}.')
    return image


def _check(root, post, stage):
    require(stage in STAGES, 'invalid_stage', f'Use one of {STAGES}.')
    root = Path(root).expanduser().resolve()
    config, policy, directory, files = _base(root, post)
    _research(root, directory, policy, files)
    if stage == 'research':
        return {'fingerprint': _revision(files), 'files': files}
    if policy.get('research'):
        receipt_path = storage.project_file(directory, 'research-review.json')
        _receipt(receipt_path, _revision(files), 'research')
        _remember(root, files, receipt_path)
    manifest, text = _content(root, directory, config, policy, files)
    image = _visual(root, directory, policy, manifest, files) if stage in ('visual', 'publish') else None
    fingerprint = _revision(files)
    approval = None
    if stage == 'publish':
        approval = _receipt(storage.project_file(directory, 'content-approval.json'), fingerprint, 'content')
        require(not image or approval.get('visual_reviewed') is True, 'visual_review',
                'Human approval must confirm the rendered PNG matches the source and brand, including typography.')
    return {'fingerprint': fingerprint, 'files': files, 'channel': manifest['channel'],
            'page_id': config['page_id'], 'copy_text': text, 'image': str(image) if image else None,
            'groups': manifest.get('groups', []), 'approval': approval}


def check(root, post, stage='publish'):
    """Return stable JSON-friendly errors; no writes, network or browser access."""
    try:
        data = _check(root, post, stage)
        return {'ok': True, 'stage': stage, 'post': post, **data}
    except (ValueError, OSError, TypeError, KeyError, AttributeError, ET.ParseError) as exc:
        return {'ok': False, 'stage': stage, 'post': post,
                'errors': [{'code': getattr(exc, 'code', 'invalid_artifact'), 'detail': str(exc)}]}


def record_decision(root, post, *, kind, reviewer, approved=False, visual_reviewed=False):
    """Record a human attestation, not a claim that a script verified legal truth."""
    require(kind in ('research', 'content'), 'invalid_decision', 'Unknown decision kind.')
    require(approved is True and text_value(reviewer), 'approval_required',
            'Explicit human approval and a named reviewer are required; agents must not self-approve.')
    result = check(root, post, 'research' if kind == 'research' else 'visual')
    require(result['ok'], 'preflight_failed', json.dumps(result.get('errors', []), ensure_ascii=False))
    require(kind != 'content' or not result.get('image') or visual_reviewed is True, 'visual_review',
            'Inspect the rendered PNG and explicitly attest --visual-reviewed.')
    receipt = {'schema_version': 1, 'kind': kind, 'approved': True, 'reviewer': reviewer,
               'approved_at': storage.now().isoformat(), 'fingerprint': result['fingerprint'],
               'visual_reviewed': bool(visual_reviewed), 'files': result['files']}
    directory = post_directory(Path(root).resolve(), post)
    storage.save(storage.project_file(directory, 'research-review.json' if kind == 'research' else 'content-approval.json'), receipt)
    return {'ok': True, 'post': post, 'decision': receipt}


def managed_projects(page_id):
    """Find policy-managed Page IDs even if the caller omitted --project."""
    if page_id is None:
        return []
    matches = []
    for path in (storage.REPO_ROOT / 'local').glob('*/loop/config.json'):
        config = read_json(path)
        if config.get('page_id') == page_id and 'content_policy' in config:
            matches.append(path.parent.parent.resolve())
    return matches


def require_publication(*, project=None, post=None, page_id=None, text, image=None, video=None, groups=None):
    """Shared guard for CLI and direct publishers, before browser and before click."""
    managed = managed_projects(page_id)
    if project is None:
        require(not managed, 'project_required', 'This Page is policy-managed; supply --project and --post.')
        require(post is None, 'project_required', '--post requires --project.')
        return page_id
    root = Path(project).expanduser().resolve()
    require(not managed or root in managed, 'page_identity', 'Page belongs to a different policy-managed project.')
    result = check(root, post, 'publish')
    require(result['ok'], 'preflight_failed', json.dumps(result.get('errors', []), ensure_ascii=False))
    require(result['channel'] == 'facebook_page', 'channel', 'Facebook Page publisher requires facebook_page content.')
    require(page_id is None or page_id == result['page_id'], 'page_identity', 'Page ID differs from project configuration.')
    require(text == result['copy_text'], 'copy_changed', 'Submitted text differs from the exact approved copy file.')
    supplied = str(Path(image).expanduser().resolve()) if image else None
    require(supplied == result['image'] and video is None, 'media_changed', 'Submitted media differs from approved content.')
    require(list(groups or []) == result['groups'], 'groups_changed', 'Group destinations differ from approved content.')
    return result['page_id']
