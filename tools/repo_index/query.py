"""Hybrid retrieval over the repository index.

Cheap-first ranking:

1. exact path / basename / symbol matches
2. IDF-weighted token overlap across path, summary, symbols, tags, ``change_when``
3. optional semantic rerank of the top candidates (TypeSafe Jev)

The first two stages are deterministic and run offline. Semantic reranking is
opt-in so a query never blocks on network access.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .indexer import (
    DEFAULT_INDEX_REL,
    SCHEMA_VERSION,
    build_index,
    quick_check,
)

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")

DOC_INTENT = {"doc", "docs", "documentation", "readme", "guide", "plan", "spec", "explain", "tutorial", "notes"}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "does",
    "for",
    "get",
    "make",
    "use",
    "using",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}


def stem(token: str) -> str:
    """Small deterministic stemmer: enough for publish/published/publishing and plurals."""
    token = token.lower()
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            if suffix == "s" and base.endswith("s"):
                continue
            return base
    return token


def tokens(text: str) -> List[str]:
    if not text:
        return []
    expanded = CAMEL_RE.sub(r"\1 \2", text)
    found = TOKEN_RE.findall(expanded)
    result: List[str] = []
    for token in found:
        lowered = token.lower()
        if len(lowered) <= 1 or lowered in STOPWORDS:
            continue
        cleaned = stem(lowered)
        if cleaned and cleaned not in STOPWORDS:
            result.append(cleaned)
    return result


def unique(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolve_index_path(root: Path, index_path: Optional[Path]) -> Path:
    if index_path is None:
        return (root / DEFAULT_INDEX_REL).resolve()
    path = Path(index_path)
    return path if path.is_absolute() else (root / path).resolve()


def load_index(
    root: Path,
    index_path: Optional[Path] = None,
    *,
    refresh: bool = True,
    quiet: bool = True,
) -> Dict[str, Any]:
    root = root.resolve()
    path = resolve_index_path(root, index_path)
    if refresh and not quick_check(root, path).get("ok"):
        build_index(root, path, write=True, quiet=quiet)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Unable to read index at {path}: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        if refresh:
            data = build_index(root, path, write=True, quiet=quiet)
        else:
            raise RuntimeError(
                f"Index schema {data.get('schema_version')} does not match {SCHEMA_VERSION}; rebuild it."
            )
    return data


def _document(entry: Dict[str, Any]) -> str:
    parts = [
        entry.get("path", ""),
        entry.get("summary", ""),
        " ".join(str(tag) for tag in entry.get("tags", [])),
        " ".join(str(symbol.get("name", "")) for symbol in entry.get("symbols", [])),
        entry.get("change_when", ""),
    ]
    return " ".join(part for part in parts if part)


def _mode_adjustment(entry: Dict[str, Any], mode: str, query_tokens: Sequence[str]) -> Tuple[float, List[str]]:
    adjustment = 0.0
    why: List[str] = []
    path = entry.get("path", "")
    kind = entry.get("kind", "")
    is_test = bool(re.search(r"(^|/)(tests?|__tests__)/|test_[^/]+\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$", path))
    query_mentions_test = any(token in {"test", "tests", "testing", "pytest"} for token in query_tokens)

    doc_intent = any(token in DOC_INTENT for token in query_tokens)

    if mode == "edit":
        if entry.get("entrypoint"):
            adjustment += 2.5
            why.append("entrypoint")
        if entry.get("tests"):
            adjustment += 1.5
            why.append("has_tests")
        if entry.get("dependents"):
            adjustment += min(2.0, 0.3 * len(entry["dependents"]))
            why.append("dependents")
        if entry.get("generated"):
            adjustment -= 10.0
            why.append("generated_penalty")
        if is_test and not query_mentions_test:
            adjustment -= 6.0
            why.append("test_penalty")
        if kind == "doc" and not doc_intent:
            adjustment -= 12.0
            why.append("doc_penalty")
    elif mode == "read":
        if kind == "doc":
            adjustment += 3.0
            why.append("doc_boost")
        if entry.get("generated"):
            adjustment -= 4.0

    if entry.get("change_when"):
        adjustment += 0.5
    return adjustment, why


def lexical_rank(
    data: Dict[str, Any],
    query: str,
    *,
    mode: str = "any",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    files: Dict[str, Any] = data.get("files", {})
    if not files:
        return []

    query_clean = " ".join(query.lower().split())
    query_tokens = unique(tokens(query))
    phrase_tokens = set(query_tokens)

    docs = {path: _document(entry) for path, entry in files.items() if isinstance(entry, dict)}
    doc_tokens = {path: set(tokens(text)) for path, text in docs.items()}
    total = max(1, len(doc_tokens))
    df: Dict[str, int] = {}
    for token_set in doc_tokens.values():
        for token in token_set:
            df[token] = df.get(token, 0) + 1
    idf = {token: math.log(1 + total / (1 + count)) for token, count in df.items()}

    results: List[Dict[str, Any]] = []
    for path, entry in files.items():
        if not isinstance(entry, dict):
            continue
        path_lower = path.lower()
        basename = Path(path).name.lower()
        stem_name = Path(path).stem.lower()
        score = 0.0
        why: List[str] = []

        if query_clean and query_clean in path_lower:
            score += 25.0
            why.append("path_phrase")
        if query_clean and query_clean == basename:
            score += 40.0
            why.append("filename_exact")
        if query_clean and query_clean == stem_name:
            score += 20.0
            why.append("stem_exact")

        summary = str(entry.get("summary", "")).lower()
        change_when = str(entry.get("change_when", "")).lower()
        summary_tokens = set(tokens(summary))
        change_tokens = set(tokens(change_when))
        path_tokens = set(tokens(path_lower))
        tags = {stem(str(tag).lower()) for tag in entry.get("tags", [])}
        symbol_names = [str(symbol.get("name", "")) for symbol in entry.get("symbols", [])]
        doc_symbol_kinds = {"h1", "h2", "h3", "h4", "h5", "h6", "key"}
        code_symbol_names = [
            str(symbol.get("name", ""))
            for symbol in entry.get("symbols", [])
            if symbol.get("kind") not in doc_symbol_kinds
        ]
        doc_symbol_names = [
            str(symbol.get("name", ""))
            for symbol in entry.get("symbols", [])
            if symbol.get("kind") in doc_symbol_kinds
        ]
        symbol_tokens = {token for name in code_symbol_names for token in tokens(name)}
        heading_tokens = {token for name in doc_symbol_names for token in tokens(name)}

        matched_terms = 0
        for token in query_tokens:
            term_score = 0.0
            if token in path_tokens or token in path_lower:
                term_score += 6.0 * idf.get(token, 1.0)
            if token in symbol_tokens:
                term_score += 8.0 * idf.get(token, 1.0)
                why.append(f"symbol:{token}")
            elif token in heading_tokens:
                term_score += 2.5 * idf.get(token, 1.0)
                why.append(f"heading:{token}")
            if token in summary_tokens:
                term_score += 4.0 * idf.get(token, 1.0)
            if token in tags:
                term_score += 5.0
                why.append(f"tag:{token}")
            if token in change_tokens:
                term_score += 7.0 * idf.get(token, 1.0)
                why.append(f"change_when:{token}")
            if term_score > 0:
                matched_terms += 1
                score += term_score
            elif any(token in name.lower() for name in symbol_names):
                matched_terms += 1
                score += 3.0 * idf.get(token, 1.0)
                why.append(f"symbol_partial:{token}")

        if phrase_tokens and matched_terms:
            score += 10.0 * (matched_terms / len(phrase_tokens))

        doc_intent = any(token in DOC_INTENT for token in query_tokens)
        if mode == "edit" and entry.get("kind") == "doc" and not doc_intent:
            score *= 0.55
            why.append("doc_multiplier")
        elif mode == "read" and entry.get("kind") != "doc":
            score *= 0.85

        adjustment, mode_why = _mode_adjustment(entry, mode, query_tokens)
        score += adjustment
        why.extend(mode_why)

        if score <= 0:
            continue

        results.append(
            {
                "path": path,
                "score": round(score, 4),
                "confidence": round(1 - math.exp(-max(score, 0) / 12), 4),
                "why": unique(why)[:12],
                "summary": str(entry.get("summary", ""))[:300],
                "kind": entry.get("kind", ""),
                "language": entry.get("language", ""),
                "symbols": symbol_names[:8],
                "tests": list(entry.get("tests", []))[:5],
                "change_when": entry.get("change_when", ""),
                "entrypoint": bool(entry.get("entrypoint")),
                "dependencies": list(entry.get("dependencies", []))[:8],
                "dependents": list(entry.get("dependents", []))[:8],
            }
        )

    results.sort(key=lambda item: (-item["score"], item["path"]))
    return results[:limit]


def semantic_rerank(
    results: List[Dict[str, Any]],
    query: str,
    root: Path,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Rerank the top candidates with TypeSafe Jev, failing open."""
    if not results:
        return results, None
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
        from typesafe_sdk import Noul, TypeSafeClient
    except Exception as exc:
        return results, f"semantic unavailable: {exc}"

    candidates = results[:30]
    questions = {}
    for index, item in enumerate(candidates):
        questions[f"cand::{index}"] = Noul(
            instructions=(
                "Could this file be the exact place to edit or read for the user's request? "
                f"Path: {item['path']}. Summary: {item.get('summary', '')}. "
                f"Symbols: {', '.join(item.get('symbols', [])[:8])}."
            )
        )

    try:
        with TypeSafeClient() as client:
            response = client.system_one(
                state={"user_request": query, "workspace": root.name},
                questions=questions,
            )
    except Exception as exc:
        return results, f"semantic failed: {exc}"

    top_score = max((item["score"] for item in candidates), default=1.0) or 1.0
    for index, item in enumerate(candidates):
        answer = response.answers.get(f"cand::{index}")
        if answer is None:
            continue
        probability = float(getattr(answer, "noul", 0.0))
        lexical = max(0.0, item["score"]) / top_score
        item["lexical_score"] = item["score"]
        item["semantic_probability"] = round(probability, 4)
        item["score"] = round((0.7 * lexical + 0.3 * probability) * 20, 4)
        item["confidence"] = round(max(0.0, min(1.0, 0.7 * lexical + 0.3 * probability)), 4)
        item["why"].append(f"semantic:{probability:.2f}")

    candidates.sort(key=lambda item: (-item["score"], item["path"]))
    return candidates + results[30:], None


def query_index(
    text: str,
    root: Path,
    index_path: Optional[Path] = None,
    *,
    top: int = 8,
    mode: str = "any",
    semantic: bool = False,
    refresh: bool = True,
) -> Dict[str, Any]:
    root = root.resolve()
    if mode not in {"any", "edit", "read"}:
        raise ValueError("mode must be one of: any, edit, read")

    data = load_index(root, index_path, refresh=refresh)
    results = lexical_rank(data, text, mode=mode, limit=max(top, 20))
    semantic_error = None
    if semantic:
        results, semantic_error = semantic_rerank(results, text, root)
        results = results[: max(top, 20)]

    final = results[:top]
    for item in final:
        item.pop("lexical_score", None)
    primary = final[0] if final else None
    return {
        "query": text,
        "mode": mode,
        "semantic": semantic and semantic_error is None,
        "semantic_error": semantic_error,
        "index": {
            "path": str(resolve_index_path(root, index_path)),
            "generated_at": data.get("generated_at"),
            "source_rev": data.get("source_rev"),
            "stats": data.get("stats", {}),
            "public": bool(data.get("public")),
        },
        "primary": primary,
        "results": final,
    }
