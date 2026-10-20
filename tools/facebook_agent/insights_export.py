"""Import Content Library daily CSV without averaging daily averages or guessing timezones."""

import csv
import base64
from datetime import datetime
import json
import math
from pathlib import Path
import re
import hashlib
import os
import time
from urllib.parse import parse_qs, urlsplit

from .models import AgentError


def validate_download(path, page_id):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if not {'Post ID', 'Page ID'}.issubset(headers):
            raise AgentError('export_failed', 'Downloaded file is not the expected Content CSV.')
        rows = 0
        posts = set()
        for row in reader:
            if row.get('Page ID') != page_id:
                raise AgentError('export_failed', 'CSV Page identity does not match the requested Page.')
            posts.add(row['Post ID'])
            rows += 1
    return {'columns': headers, 'rows': rows, 'posts': len(posts)}


def report_id_from_url(url):
    parsed = urlsplit(url)
    target = parse_qs(parsed.query).get('u', [url])[0]
    target = urlsplit(target)
    if target.scheme != 'https' or not (target.hostname or '').endswith('.fbcdn.net'):
        return None
    match = re.search(r'\.(\d+)$', target.path)
    return match[1] if match else None


def reconcile_report(directory, page_id, report_id):
    """Reuse verified local evidence; an uncertain prior click is not permission to retry."""
    uncertain = []
    for audit in sorted(Path(directory).glob('*.export.json')):
        try:
            data = json.loads(audit.read_text())
        except (OSError, ValueError):
            continue
        profile = data.get('profile', {})
        query = parse_qs(urlsplit(profile.get('url', '')).query)
        if data.get('report_id') != report_id or query.get('id') != [page_id]:
            continue
        if data.get('status') == 'downloaded':
            path = Path(data.get('output', ''))
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == data.get('sha256'):
                metrics = validate_download(path, page_id)
                return {'status': 'reused', 'output': str(path), 'audit': str(audit),
                        'report_id': report_id, **metrics}
            uncertain.append(str(audit))
        elif data.get('status') in ('download_requested', 'download_not_received'):
            uncertain.append(str(audit))
    if uncertain:
        raise AgentError('export_uncertain', 'A prior download may have succeeded. Reconcile these audits and local downloads before retrying: ' + ', '.join(uncertain), True)
    return None


def export_csv(browser, page_id, output, download_timeout_seconds=90, report_id=None, breakdown='summary'):
    """Create one Content report via the UI and capture its browser download."""
    from datetime import datetime, timezone
    from . import selectors
    from .insights import SNAPSHOT

    output = Path(output)
    audit = output.with_suffix('.export.json')
    staging = output.with_suffix('.csv.download')
    if output.suffix.lower() != '.csv':
        raise AgentError('invalid_arguments', 'Output must be a .csv path.')
    if not 1 <= download_timeout_seconds <= 300:
        raise AgentError('invalid_arguments', 'Download timeout must be between 1 and 300 seconds.')
    if breakdown not in ('summary', 'daily'):
        raise AgentError('invalid_arguments', 'Breakdown must be "summary" or "daily".')
    if report_id is not None and (not report_id.isascii() or not report_id.isdigit()):
        raise AgentError('invalid_arguments', 'Report ID must contain ASCII digits only.')
    if report_id is not None:
        existing = reconcile_report(output.parent, page_id, report_id)
        if existing:
            return existing
    if any(path.exists() for path in (output, audit, staging)):
        raise AgentError('invalid_arguments', 'Choose a new .csv path; CSV, audit and staging paths must not exist.')
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = browser.check_authenticated(page_id=page_id)
    page = browser.page
    browser.keep_page = True
    result = {'profile': profile, 'source_url': 'https://www.facebook.com/professional_dashboard/content/content_library/',
              'status': 'preparing', 'report_id': report_id, 'breakdown': breakdown, 'output': str(output), 'records': []}

    def record(stage):
        selectors.check_block(page)
        snapshot = {'stage': stage, 'observed_at': datetime.now(timezone.utc).isoformat(),
                    'url': page.url, **page.evaluate(SNAPSHOT)}
        image = output.with_name(output.stem + f'-export-{len(result["records"]):02d}.png')
        page.screenshot(path=str(image), full_page=True)
        snapshot['screenshot'] = image.name
        result['records'].append(snapshot)
        audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

    downloads = []
    popups = []
    def on_download(download):
        downloads.append(download)
    def on_popup(popup):
        popups.append(popup)
        popup.on('download', on_download)
    page.on('download', on_download)
    page.on('popup', on_popup)

    def open_menu(label):
        selectors.unique(selectors.visible(page.get_by_role('button', name='Export data', exact=True)), 'Export data').click()
        item = page.get_by_role('menuitem', name=label, exact=True).or_(
            page.get_by_role('button', name=label, exact=True))
        selectors.visible(item).first.wait_for(state='visible')
        selectors.unique(selectors.visible(item), label).click()
        dialogs = selectors.visible(page.get_by_role('dialog'))
        dialogs.first.wait_for(state='visible')
        return selectors.unique(dialogs, label + ' dialog')

    def report_links(dialog):
        links = dialog.locator('a[href]').filter(has_text=re.compile(r'^Download$'))
        return {identity: links.nth(index) for index in range(links.count())
                if (identity := report_id_from_url(links.nth(index).get_attribute('href') or ''))}

    try:
        page.goto(result['source_url'], wait_until='domcontentloaded', timeout=browser.timeout_ms)
        page.wait_for_timeout(5000)
        record('library')
        history = open_menu('Report history')
        page.wait_for_timeout(1500)
        existing = set(report_links(history))
        result['existing_report_ids'] = sorted(existing)
        if report_id is None:
            selectors.unique(selectors.visible(history.get_by_role('button', name='Close', exact=True)), 'Close history').click()
            dialog = open_menu('Create new data report')
            dialog.get_by_text('Create data report', exact=True).wait_for()
            content = dialog.get_by_role('button', name=re.compile(r'^Content\s+View data'))
            selectors.unique(selectors.visible(content), 'Content report type').click()
            result['settings_displayed'] = dialog.inner_text()
            record('report-settings')
            create = selectors.unique(selectors.visible(dialog.get_by_role('button', name='Create report (.csv)', exact=True)), 'Create report')
            result['status'] = 'creation_requested'
            audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            create.click()  # Exactly one report request; never retry automatically.
            page.wait_for_timeout(2000)
            if not downloads:
                try:
                    done_btn = dialog.get_by_role('button', name=re.compile(r'^(?:Done|Close|Xong|Đóng)$', re.I))
                    if done_btn.count() > 0 and done_btn.first.is_visible():
                        done_btn.first.click()
                except Exception:
                    pass
                try:
                    dialog.wait_for(state='hidden', timeout=10000)
                except Exception:
                    pass
                try:
                    page.get_by_role('button', name='Export data', exact=True).wait_for(state='visible', timeout=10000)
                except Exception:
                    pass
                history = open_menu('Report history')
        deadline = time.monotonic() + download_timeout_seconds
        clicked_download = False
        while not downloads and time.monotonic() < deadline:
            page.wait_for_timeout(1000)
            selectors.check_block(page)
            if clicked_download:
                continue
            available = report_links(history)
            candidates = {report_id} & set(available) if report_id else set(available) - existing
            if len(candidates) > 1:
                raise AgentError('export_failed', 'Multiple new reports appeared; choose the explicit report ID to download.', True)
            if len(candidates) == 1:
                result['report_id'] = next(iter(candidates))
                existing_download = reconcile_report(output.parent, page_id, result['report_id'])
                if existing_download:
                    result['status'] = 'reused'
                    result['reused_output'] = existing_download['output']
                    audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
                    return existing_download
                result['status'] = 'download_requested'
                record('report-history')
                available[result['report_id']].click()
                clicked_download = True
        if not downloads:
            result['status'] = 'download_not_received'
            result['popup_evidence'] = [
                {'url': popup.url, **popup.evaluate(SNAPSHOT)}
                for popup in popups if not popup.is_closed()]
            record('download-not-received')
            raise AgentError('export_failed', f'Report download was not received. Inspect {audit} and the preserved tab before requesting another report.', True)
        download = downloads[0]
        download.save_as(str(staging))
        result['csv'] = validate_download(staging, page_id)
        result['suggested_filename'] = download.suggested_filename
        result['sha256'] = hashlib.sha256(staging.read_bytes()).hexdigest()
        # Exclusive publication: never replace a user file that appeared during export.
        os.link(staging, output)
        staging.unlink()
        result['status'] = 'downloaded'
        record('downloaded')
        return {'status': result['status'], 'output': str(output), 'audit': str(audit),
                'suggested_filename': result['suggested_filename'], **result['csv']}
    except Exception as exc:
        result['error'] = str(exc)
        audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        page.remove_listener('download', on_download)
        page.remove_listener('popup', on_popup)


METRICS = {'Average Seconds viewed': 'average_seconds_viewed', 'Comments': 'comments',
           'Reactions': 'reactions', 'Shares': 'shares', 'Seconds viewed': 'seconds_viewed'}


def enrich_snapshot(record):
    from .insights import post_metrics
    segments = []
    for segment in record.get('age_gender_segments', []):
        width = segment.get('bar_width', '')
        if re.fullmatch(r'\d+(?:\.\d+)?%', width):
            segments.append({'age': segment['age'], 'gender': segment['gender'],
                             'percentage': float(width[:-1]),
                             'method': 'rendered data-metric gender label and percentage-width bar',
                             'row_text': segment.get('row_text')})
    discovery = []
    for panel in record.get('discovery_panels', []):
        text = panel['text'].replace('\ufeff', '')
        pairs = re.findall(r'^([^\n]+)\n(\d+(?:\.\d+)?)%$', text, re.M)
        discovery.append({'tab': panel.get('selected_tab'),
                          'percentages': {label: float(value) for label, value in pairs},
                          'raw_text': panel['text']})
    return {'stage': record['stage'], 'observed_at': record['observed_at'],
            'metrics': record.get('post_metrics') or post_metrics(record['text']),
            'age_and_gender': segments, 'how_people_find_content': discovery,
            'demographic_evidence': record.get('chart_tooltips', [])}


def import_export(csv_path, output, page_id, dashboard_files=(), breakdown=None):
    output = Path(output)
    if output.exists():
        raise AgentError('invalid_arguments', 'Output already exists; choose a new path.')
    posts = {}
    row_count = duplicates = 0
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or [])
        base_required = {'Post ID', 'Page ID', 'Publish time', 'Permalink'}
        if not base_required.issubset(headers):
            raise AgentError('invalid_arguments', 'CSV is missing base Content Library columns.')
        is_daily = 'Date' in headers
        if breakdown == 'daily' and not is_daily:
            raise AgentError('invalid_arguments', 'Requested daily breakdown but CSV does not contain a Date column.')
        if breakdown == 'summary' and is_daily:
            raise AgentError('invalid_arguments', 'Requested summary breakdown but CSV contains a daily Date column.')
        detected_breakdown = 'daily' if is_daily else 'summary'

        for row in reader:
            row_count += 1
            if row['Page ID'] != page_id:
                raise AgentError('invalid_arguments', 'CSV contains a different Page ID.')
            post_id = row['Post ID']
            if not post_id.isascii() or not post_id.isdigit():
                raise AgentError('invalid_arguments', 'Invalid Post ID.')
            entry = posts.setdefault(post_id, {
                'post_id': post_id, 'page_id': page_id, 'title': row.get('Title'),
                'permalink': row['Permalink'], 'post_type': row.get('Post type'),
                'duration_seconds': float(row['Duration (sec)']) if row.get('Duration (sec)') else None,
                'publish_time_raw': row['Publish time'], 'publish_timezone': None,
                'breakdown': detected_breakdown,
                'daily': [], 'dashboard_snapshots': [],
            })
            if (entry['permalink'], entry['publish_time_raw']) != (row['Permalink'], row['Publish time']):
                raise AgentError('invalid_arguments', 'Conflicting metadata for one Post ID.')

            if is_daily:
                day = {'date': datetime.strptime(row['Date'], '%m/%d/%Y').date().isoformat(),
                       'data_comment': row.get('Data comment') or None}
                for header, key in METRICS.items():
                    if header in row:
                        value = row[header].strip()
                        day[key] = float(value) if value not in ('', '--', 'N/A') else None
                        if day[key] is not None and (not math.isfinite(day[key]) or day[key] < 0):
                            raise AgentError('invalid_arguments', 'CSV metrics must be finite nonnegative values.')
                previous = next((item for item in entry['daily'] if item['date'] == day['date']), None)
                if previous:
                    if previous != day:
                        raise AgentError('invalid_arguments', 'Conflicting rows for one post/day; refusing double count.')
                    duplicates += 1
                    continue
                entry['daily'].append(day)
            else:
                summary_row = {}
                for header, key in METRICS.items():
                    if header in row:
                        value = row[header].strip()
                        summary_row[key] = float(value) if value not in ('', '--', 'N/A') else None
                        if summary_row[key] is not None and (not math.isfinite(summary_row[key]) or summary_row[key] < 0):
                            raise AgentError('invalid_arguments', 'CSV metrics must be finite nonnegative values.')
                if 'summary_metrics' in entry:
                    if entry['summary_metrics'] != summary_row:
                        raise AgentError('invalid_arguments', 'Conflicting summary rows for one Post ID.')
                    duplicates += 1
                    continue
                entry['summary_metrics'] = summary_row

    for entry in posts.values():
        if entry['breakdown'] == 'daily':
            entry['daily'].sort(key=lambda item: item['date'])
            entry['export_period_totals'] = {}
            for key in ('comments', 'reactions', 'shares', 'seconds_viewed'):
                values = [item[key] for item in entry['daily'] if key in item]
                entry['export_period_totals'][key] = sum(values) if all(v is not None for v in values) and values else None
            entry['average_seconds_viewed_aggregate'] = None
        else:
            entry['export_period_totals'] = entry.get('summary_metrics', {})
            entry['average_seconds_viewed_aggregate'] = entry.get('summary_metrics', {}).get('average_seconds_viewed')
    unmatched = []
    for path in dashboard_files:
        data = json.loads(Path(path).read_text())
        if data.get('profile', {}).get('url', '').split('id=')[-1] != page_id:
            raise AgentError('invalid_arguments', 'Dashboard evidence has a different Page identity.')
        for record in data.get('records', []):
            query = parse_qs(urlsplit(record['url']).query)
            content = query.get('content_id', [''])[0]
            if not content:
                continue
            identity = base64.b64decode(content, validate=True).decode().split(':')
            if len(identity) < 4 or identity[1] != '_I' + page_id:
                raise AgentError('invalid_arguments', 'Dashboard content identity does not match Page.')
            post_id = identity[2]
            snapshot = {'source_file': str(path), **enrich_snapshot(record)}
            if post_id in posts:
                posts[post_id]['dashboard_snapshots'].append(snapshot)
            else:
                unmatched.append({'post_id': post_id, **snapshot})
    data = {'page_id': page_id, 'source_csv': str(csv_path),
            'source_rows': row_count, 'duplicate_rows_ignored': duplicates,
            'posts': list(posts.values()), 'unmatched_dashboard_snapshots': unmatched,
            'limits': [
                'CSV daily metrics and dashboard cumulative metrics have different windows; never add them together.',
                'CSV does not contain views, viewers, age, gender or discovery sources. Missing fields are unknown.',
                'Publish time timezone is unspecified; do not use it to change 24h due times.',
                'Daily average seconds viewed cannot be summed or averaged across days without its denominator.',
                'Pre-publication zero rows are export padding, not evidence of historical distribution.',
            ]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return {'posts': len(posts), 'source_rows': row_count, 'output': str(output),
            'unmatched_dashboard_snapshots': len(unmatched)}
