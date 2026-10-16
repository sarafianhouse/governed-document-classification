"""Evidence-based document classifier.

Pure functions: no file, network or database I/O. Every decision carries its evidence,
a confidence score and a human-review flag. Nothing here moves files or changes labels.
"""
import json
import hashlib
import re
import urllib.parse
from collections import Counter
from datetime import datetime, timezone


ENGINE_VERSION = "attribute-classifier-v2.2.2"
MEDIA_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "tif", "tiff", "bmp", "wmv", "mp4", "mov", "avi"}
LEGACY_EXTENSIONS = {"ppt": "Presentation", "xls": "Spreadsheet"}
SIZE_SKIP_EXTENSIONS = {"pptx": "Presentation", "xlsx": "Spreadsheet", "ppt": "Presentation", "xls": "Spreadsheet"}
CONFIDENCE_THRESHOLDS = {"high": 85, "medium": 60}


def _text(record):
    return record.get("fullText") or ""


def _evidence(record, signal):
    extension = _extension(record)
    pages = record.get("pages") or []
    if signal == "presentationStructure" and extension in {"ppt", "pptx"} and pages:
        return {"signal": signal, "value": f"{len(pages)} extracted slides"}
    if signal == "spreadsheetStructure" and extension in {"xls", "xlsx"} and pages:
        return {"signal": signal, "value": f"{len(pages)} extracted worksheets"}
    if signal == "mediaFileType" and extension in MEDIA_EXTENSIONS:
        return {"signal": signal, "value": f"media file type .{extension}"}
    if signal == "productSpecFilename":
        match = re.search(r"sup(?:plement)?[\s_-]*facts|formula|spec(?:ification)?s?\b", record.get("filename") or "", re.IGNORECASE)
        return {"signal": signal, "value": f"filename: {match.group(0)}"} if match else None
    attributes = record.get("attributes") or {}
    identifiers = attributes.get("identifiers") or {}
    dates = attributes.get("dates") or {}
    financial = attributes.get("financial") or {}
    signal_map = {
        "invoiceNumber": identifiers.get("invoiceNumber"),
        "invoiceDate": dates.get("invoiceDate"),
        "amountDue": financial.get("amountDue"),
        "invoiceTotal": financial.get("total"),
        "subtotal": financial.get("subtotal"),
        "tax": financial.get("tax"),
        "paymentTerms": financial.get("paymentTerms"),
        "purchaseOrderNumber": identifiers.get("purchaseOrderNumber"),
        "contractNumber": identifiers.get("contractNumber"),
        "effectiveDate": dates.get("effectiveDate"),
        "expirationDate": dates.get("expirationDate"),
        "terminationDate": dates.get("terminationDate"),
        "renewalDate": dates.get("renewalDate"),
    }
    if signal in signal_map:
        value = signal_map[signal]
        return {"signal": signal, "value": value} if value not in (None, "", []) else None
    patterns = {
        "invoiceHeading": r"\binvoice\b",
        "billTo": r"\bbill\s+to\b",
        "quoteLanguage": r"\b(?:quote|quotation|quoted)\b",
        "purchaseOrderLanguage": r"\bpurchase\s+order\b|\bP\.?O\.?\s*(?:number|no\.?|#)",
        "contractLanguage": r"\bcontract\b",
        "agreementLanguage": r"\bagreement\b",
        "partyLanguage": r"\bparties\b|\bcounterparty\b|\bbetween\s+.+\s+and\s+.+",
        "governingLaw": r"\bgoverning\s+law\b",
        "signatureLanguage": r"\b(?:signed|signature|executed\s+by)\b",
        "lineItemLanguage": r"\b(?:line\s+items?|quantity|unit\s+price)\b",
        "receiptLanguage": r"\b(?:receipt|transaction\s+id|payment\s+method)\b",
        "reportLanguage": r"\b(?:report|analysis|findings)\b",
        "correspondenceLanguage": r"\b(?:from|to|subject)\s*:",
        "policyLanguage": r"\bpolicy\b",
        "procedureLanguage": r"\bprocedure\b|\bstandard\s+operating\s+procedure\b",
        "marketingLanguage": r"\b(?:marketing|advertis(?:e|ement|ing)|print\s+ad|promotion(?:al)?|product\s+benefits|claims|brand|launch|press\s+release|consumer)\b|\bthese\s+statements\s+have\s+not\s+been\s+evaluated\b|\bavailable\s+at\s*:|\btry\s+.{1,40}\s+today\b",
        "supplementFactsLanguage": r"\bsupplement\s+facts\b|\bserving\s+size\b|\bservings\s+per\s+container\b|%\s*daily\s+value",
        "formulaLanguage": r"\bformula(?:tion)?\b|\bproduct\s+spec(?:ification)?s?\b|\bmg\s+per\s+serving\b",
        "ingredientLanguage": r"\b(?:other\s+)?ingredients\b|\bextract\b|\bproprietary\s+blend\b",
        "productIdentifier": r"\b(?:sku|upc|item\s*(?:#|no\.?|number)|\d+\s*(?:ct|count))\b",
        "sellSheetLanguage": r"\bsell\s+sheet\b|\bcase\s+pack\b|\bpallet\b|\bsrp\b|\bmsrp\b|\bretail\s+price\b|\bunit\s+cost\b",
        "retailerLanguage": r"\bretailers?\b|\bbuyer\b|\bplanogram\b|\bsell[\s-]?in\b|\bline\s+review\b",
        "letterLanguage": r"\bdear\s+\w+|\bhi\s+\w+\s*,|\bplease\s+find\s+(?:the\s+)?enclosed\b|\bsincerely\b|\bbest\s+regards\b|\bsamples?\s+(?:enclosed|attached|letter)\b",
        "technicalLanguage": r"\b(?:technical\s+specification|architecture|system\s+requirements)\b",
        "financialLanguage": r"\b(?:balance\s+sheet|profit\s+and\s+loss|cash\s+flow|financial\s+statement)\b",
    }
    pattern = patterns.get(signal)
    if not pattern:
        return None
    match = re.search(pattern, _text(record), re.IGNORECASE)
    return {"signal": signal, "value": match.group(0)} if match else None


def _extension(record):
    return (record.get("filename") or "").rsplit(".", 1)[-1].casefold()


TAG_KEYS = ("retailers", "products", "brands", "partners")
_DATE_YEAR_PATTERNS = (
    # (pattern, group holding the year); two-digit years are read as 20xx
    (re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)"), 1),                                      # 2014, 2012-09-18
    (re.compile(r"(?<!\d)\d{1,2}[-_. ]\d{1,2}[-_. ](\d{4}|\d{2})(?!\d)"), 1),               # 4-3-2014, 03-09-12, 5 28 14
    (re.compile(r"(?<!\d)(?:0[1-9]|1[0-2])(?:[0-2]\d|3[01])((?:19|20)\d{2})(?!\d)"), 1),    # 02202012
)


def _normalize_segment(segment):
    """Lower-case a folder or file-name segment and strip numbering and separators."""
    text = (segment or "").casefold()
    text = re.sub(r"^\d+[_\s.-]+(?=[a-z.])", "", text)
    text = re.sub(r"[_\-.\[\]{}]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def relative_path_from_url(url):
    """Turn a SharePoint/OneDrive webUrl (dbo.Documents.FilePath) into a library-relative path.

    https://tenant.sharepoint.com/sites/{site}/{library}/A/B/file.pdf      -> A/B/file.pdf
    https://tenant-my.sharepoint.com/personal/{user}/{library}/A/file.pdf  -> A/file.pdf
    Non-URLs are returned unchanged.
    """
    text = url or ""
    if not re.match(r"^https?://", text, re.IGNORECASE):
        return text
    path = urllib.parse.unquote(urllib.parse.urlsplit(text).path)
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 3 and parts[0].casefold() in ("sites", "teams", "personal"):
        parts = parts[3:]
    return "/".join(parts)


def _path_parts(record):
    """Return (folder segments, file-name stem) from sourcePath/path/filePath, with \\ or / separators."""
    raw = record.get("sourcePath") or record.get("path") or record.get("filePath") or ""
    is_url = bool(re.match(r"^https?://", raw, re.IGNORECASE))
    raw = relative_path_from_url(raw)
    parts = [part for part in re.split(r"[\\/]+", raw) if part.strip()]
    filename = record.get("filename") or ""
    if is_url and parts:
        # A webUrl always ends with the file itself.
        filename = filename or parts[-1]
        parts = parts[:-1]
    elif parts and filename and parts[-1].casefold() == filename.casefold():
        parts = parts[:-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return parts, stem


def _year_from(text, policy):
    text = re.sub(policy.get("ignoreParenthetical") or r"(?!x)x", " ", text or "", flags=re.IGNORECASE)
    low, high = policy.get("minimum", 1995), policy.get("maximum", 2100)
    for pattern, group in _DATE_YEAR_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(group)
            year = int(value) if len(value) == 4 else 2000 + int(value)
            if low <= year <= high:
                return year
    return None


# Lifecycle tags that are only trusted from folder names, never from the file name
# ("Old Price List.xlsx" is not an archive; "Family Size Spec.pdf" is not personal media).
FOLDER_ONLY_LIFECYCLE = ("Archive", "Personal Media")


def analyze_path(record, rules):
    """Derive folder signals and search tags from a document's path. Pure function; no I/O."""
    config = (rules or {}).get("pathEvidence") or {}
    empty = {"enabled": False, "folders": [], "signals": [], "classHint": None, "businessFunctionHint": None,
             "tags": {key: [] for key in TAG_KEYS} | {"periodYear": None, "lifecycle": []}}
    if not config.get("enabled"):
        return empty
    folders, stem = _path_parts(record)
    noise = [re.compile(rf"^(?:{pattern})$") for pattern in config.get("noiseSegments", [])]
    lifecycle_patterns = {name: re.compile(pattern) for name, pattern in (config.get("lifecycleSignals") or {}).items()}
    lifecycle = []
    useful = []
    for depth, raw in enumerate(folders):
        normalized = _normalize_segment(raw)
        for name, pattern in lifecycle_patterns.items():
            if pattern.search(normalized) and name not in lifecycle:
                lifecycle.append(name)
        core = _normalize_segment(re.sub(r"\(.*?\)", " ", raw))
        if not core or any(pattern.match(core) for pattern in noise):
            continue
        useful.append({"depth": depth, "raw": raw, "normalized": core})
    stem_normalized = _normalize_segment(stem)
    for name, pattern in lifecycle_patterns.items():
        if name not in FOLDER_ONLY_LIFECYCLE and pattern.search(stem_normalized) and name not in lifecycle:
            lifecycle.append(name)

    signals = []
    for name, spec in (config.get("folderSignals") or {}).items():
        pattern = re.compile(spec["pattern"])
        for folder in useful:
            match = pattern.search(folder["normalized"])
            if match:
                signals.append({"signal": name, "source": "path", "value": folder["raw"], "match": match.group(0),
                                "depth": folder["depth"], "classHint": spec.get("classHint"),
                                "businessFunction": spec.get("businessFunction")})
    tags = {key: [] for key in TAG_KEYS}
    entity_hits = []
    for key in TAG_KEYS:
        for canonical, pattern in ((config.get("entities") or {}).get(key) or {}).items():
            compiled = re.compile(pattern)
            in_folder = next((f for f in useful if compiled.search(f["normalized"])), None)
            in_name = compiled.search(stem_normalized)
            if in_folder or in_name:
                tags[key].append(canonical)
                entity_hits.append({"tag": key, "value": canonical, "foundIn": "folder" if in_folder else "filename",
                                    "segment": in_folder["raw"] if in_folder else stem})
                if key == "retailers" and in_folder:
                    signals.append({"signal": "pathRetailer", "source": "path", "value": in_folder["raw"], "match": canonical,
                                    "depth": in_folder["depth"], "classHint": None, "businessFunction": "Sales"})
    year_policy = config.get("periodYear") or {}
    year = _year_from(stem, year_policy)
    if year is None:
        for folder in reversed(useful):
            year = _year_from(folder["raw"], year_policy)
            if year:
                break
    signals.sort(key=lambda item: (-item["depth"], item["signal"]))
    class_hint = next((item for item in signals if item.get("classHint")), None)
    function_hint = next((item for item in signals if item.get("businessFunction")), None)
    tags["periodYear"] = year
    tags["lifecycle"] = lifecycle
    return {
        "enabled": True,
        "folders": [folder["raw"] for folder in useful],
        "signals": signals,
        "entityEvidence": entity_hits,
        "classHint": class_hint,
        "businessFunctionHint": function_hint,
        "tags": tags,
    }


def _path_signal_evidence(path_info, signal):
    hit = next((item for item in path_info.get("signals", []) if item["signal"] == signal), None)
    if not hit:
        return None
    return {"signal": signal, "source": "path", "value": hit["value"], "match": hit["match"]}


def merge_path_context(entries):
    """Merge path tags across copies of one file (for example an exact-duplicate group).

    entries: iterable of {"sourceItemId", "sourcePath", "pathTags"}. Returns merged tags plus the
    list of every distinct path so a kept copy retains the context of removed copies.
    """
    merged = {key: [] for key in TAG_KEYS}
    years, lifecycle, paths = [], [], []
    for entry in entries:
        tags = entry.get("pathTags") or {}
        for key in TAG_KEYS:
            for value in tags.get(key) or []:
                if value not in merged[key]:
                    merged[key].append(value)
        if tags.get("periodYear"):
            years.append(tags["periodYear"])
        for value in tags.get("lifecycle") or []:
            if value not in lifecycle:
                lifecycle.append(value)
        if entry.get("sourcePath") and entry["sourcePath"] not in paths:
            paths.append(entry["sourcePath"])
    merged["periodYear"] = min(years) if years else None
    merged["periodYears"] = sorted(set(years))
    merged["lifecycle"] = lifecycle
    return {"pathTags": merged, "paths": paths}


def _content_candidates(record, rules, path_info=None):
    candidates = []
    path_config = (rules or {}).get("pathEvidence") or {}
    path_info = path_info or {"signals": []}
    for rule in rules.get("rules", []):
        required = [_evidence(record, signal) for signal in rule.get("requiredSignals", [])]
        required_found = [item for item in required if item]
        if len(required_found) < rule.get("minimumRequiredSignals", 1):
            continue
        supporting = [_evidence(record, signal) for signal in rule.get("supportingSignals", [])]
        supporting_found = [item for item in supporting if item]
        contradictory = [_evidence(record, signal) for signal in rule.get("contradictorySignals", [])]
        contradictory_found = [item for item in contradictory if item]
        calculation = rule.get("confidenceCalculation", {})
        raw = calculation.get("base", 0)
        raw += len(required_found) * calculation.get("requiredSignalWeight", 0)
        raw += len(supporting_found) * calculation.get("supportingSignalWeight", 0)
        raw -= len(contradictory_found) * calculation.get("contradictorySignalPenalty", 0)
        path_found = [item for item in (_path_signal_evidence(path_info, signal) for signal in rule.get("pathSupportingSignals", [])) if item]
        text_score = max(0, min(100, int(raw)))
        path_bonus = min(len(path_found) * path_config.get("supportingSignalWeight", 0), path_config.get("maximumPathBonus", 0))
        score = max(0, min(100, text_score + path_bonus))
        corroboration = path_config.get("pathCorroboration") or {}
        # Two independent sources agree: strong text evidence just under HIGH plus a folder for the same class,
        # with nothing in the text contradicting it. Competing rules are still penalized afterwards.
        corroborated = bool(
            corroboration.get("enabled")
            and path_found
            and not contradictory_found
            and text_score >= int(corroboration.get("minimumTextScore", CONFIDENCE_THRESHOLDS["high"]))
        )
        if (
            not path_config.get("pathBonusCanCrossHighThreshold", False)
            and not corroborated
            and text_score < CONFIDENCE_THRESHOLDS["high"]
        ):
            score = min(score, CONFIDENCE_THRESHOLDS["high"] - 1)
        path_bonus = score - text_score
        candidates.append(
            {
                "ruleId": rule["ruleId"],
                "targetClass": rule["targetClass"],
                "score": score,
                "textScore": text_score,
                "requiredEvidence": required_found,
                "supportingEvidence": supporting_found + path_found,
                "pathBonus": path_bonus,
                "pathCorroborated": corroborated and score >= CONFIDENCE_THRESHOLDS["high"] > text_score,
                "contradictoryEvidence": contradictory_found,
                "businessFunction": rule.get("businessFunction"),
                "routingRecommendation": rule.get("routingRecommendation"),
                "specificity": rule.get("specificity", 0),
            }
        )
    # Rank on text evidence only, so folder names can raise confidence but never pick the winning class.
    return sorted(candidates, key=lambda item: (-item["textScore"], -item["specificity"], item["ruleId"]))


def _classes_compatible(first, second, rules):
    if first == second:
        return True
    policy = rules.get("competingRulePolicy") or {}
    if not policy.get("appliesOnlyToConflictingClasses"):
        return False
    return any(first in group and second in group for group in policy.get("compatibleClassGroups", []))


def _fallback_candidate(record):
    extension = _extension(record)
    text = _text(record)
    if extension in {"ppt", "pptx"} and record.get("pages"):
        return "Presentation", "document structure: slides"
    if extension == "xlsx" or (extension == "xls" and record.get("pages")):
        return "Spreadsheet", "document structure: workbook"
    candidates = [
        ("Quote", "quoteLanguage"),
        ("Receipt", "receiptLanguage"),
        ("Report", "reportLanguage"),
        ("Correspondence", "correspondenceLanguage"),
        ("Policy", "policyLanguage"),
        ("Procedure", "procedureLanguage"),
        ("Marketing Material", "marketingLanguage"),
        ("Financial Document", "financialLanguage"),
        ("Technical Document", "technicalLanguage"),
    ]
    for target, signal in candidates:
        evidence = _evidence(record, signal)
        if evidence:
            return target, evidence["value"]
    if text:
        return "Other", "Readable text present; no v1 rule matched"
    return "Other", "No readable text available"


def _split_format_topic(candidates, rules):
    format_ids = set((rules.get("formatRules") or {}).get("ruleIds", []))
    if not format_ids:
        return candidates, None
    formats = [c for c in candidates if c["ruleId"] in format_ids]
    topics = [c for c in candidates if c["ruleId"] not in format_ids]
    if not formats:
        return candidates, None
    return formats + topics[:1], (topics[0] if topics else None)


def classify_document(record, rules):
    path_info = analyze_path(record, rules)
    path_config = (rules or {}).get("pathEvidence") or {}
    class_hint = path_info.get("classHint")
    path_only = False
    candidates, topic = _split_format_topic(_content_candidates(record, rules, path_info), rules)
    best = candidates[0] if candidates else None
    fallback = None
    legacy = (rules.get("legacyFormatFallback") or {})
    legacy_class = LEGACY_EXTENSIONS.get(_extension(record)) if legacy else None
    if legacy.get("includeSizeSkippedOffice") and not legacy_class and record.get("skipReason") == "FILE_SIZE_THRESHOLD_EXCEEDED":
        legacy_class = SIZE_SKIP_EXTENSIONS.get(_extension(record))
    if best is None and legacy_class:
        score = int(legacy.get("score", 60))
        content_class = legacy_class
        matched_rules = ["LEGACY-FORMAT"]
        positive = [{"signal": "legacyFileType", "value": f".{_extension(record)} ({legacy.get('note', 'file type only')})"}]
        contradictory = []
        business_function = None
        destination = "Intake / Exception Review"
        fallback = {"targetClass": legacy_class}
    elif best is None and class_hint:
        fallback_policy = path_config.get("pathOnlyFallback") or {}
        text_target, text_evidence = _fallback_candidate(record)
        score = int(fallback_policy.get("score", 65))
        positive = [{"signal": class_hint["signal"], "source": "path", "value": class_hint["value"], "match": class_hint["match"]}]
        if text_target == class_hint["classHint"]:
            score += int(fallback_policy.get("agreeingTextBonus", 5))
            positive.append({"signal": "fallback", "value": text_evidence})
        score = min(score, int(fallback_policy.get("maximumScore", 75)), CONFIDENCE_THRESHOLDS["high"] - 1)
        content_class = class_hint["classHint"]
        fallback = {"targetClass": content_class, "score": score, "evidence": f"folder: {class_hint['value']}"}
        matched_rules = ["PATH-HINT"]
        contradictory = []
        business_function = class_hint.get("businessFunction")
        destination = "Intake / Exception Review"
        path_only = True
    elif best is None:
        target, evidence = _fallback_candidate(record)
        fallback = {"targetClass": target, "score": 45 if target not in ("Other",) else 0, "evidence": evidence}
        score = fallback["score"]
        content_class = target if score >= CONFIDENCE_THRESHOLDS["medium"] else None
        matched_rules = []
        positive = [{"signal": "fallback", "value": evidence}]
        contradictory = []
        business_function = None
        destination = "Intake / Exception Review"
    else:
        score = best["score"]
        content_class = best["targetClass"] if score >= CONFIDENCE_THRESHOLDS["medium"] else None
        matched_rules = [candidate["ruleId"] for candidate in candidates]
        positive = best["requiredEvidence"] + best["supportingEvidence"]
        contradictory = best["contradictoryEvidence"]
        business_function = best["businessFunction"] or (topic or {}).get("businessFunction")
        destination = best["routingRecommendation"] or "Intake / Exception Review"
        policy = rules.get("competingRulePolicy") or {}
        window = policy.get("window", 10)
        penalty = policy.get("penalty", 15)
        rivals = candidates[1:] if topic is None else [c for c in candidates[1:] if c is not topic]
        # Rivalry is judged on text scores so a path bonus can never create a competing-rule penalty.
        rival = next((c for c in rivals if c["textScore"] >= best["textScore"] - window and not _classes_compatible(best["targetClass"], c["targetClass"], rules)), None)
        if rival:
            contradictory.append({"signal": "competingRule", "value": rival["targetClass"], "score": rival["textScore"]})
            score = max(0, score - penalty)
            if score < CONFIDENCE_THRESHOLDS["medium"]:
                content_class = None
                destination = "Intake / Exception Review"
    business_function_source = "rule" if business_function else None
    if not business_function and path_info.get("businessFunctionHint"):
        business_function = path_info["businessFunctionHint"]["businessFunction"]
        business_function_source = "path"
    topic_class = topic["targetClass"] if topic else None
    topic_source = "content" if topic else None
    if not topic_class and class_hint and not path_only and class_hint["classHint"] != content_class:
        topic_class = class_hint["classHint"]
        topic_source = "path"
    band = "HIGH" if score >= CONFIDENCE_THRESHOLDS["high"] else "MEDIUM" if score >= CONFIDENCE_THRESHOLDS["medium"] else "LOW"
    extraction_status = record.get("extractionStatus")
    extraction_incomplete = extraction_status != "SUCCESS"
    review_required = band != "HIGH" or content_class is None or bool(contradictory) or extraction_incomplete
    review_reasons = []
    if band != "HIGH" or content_class is None:
        review_reasons.append("Confidence below HIGH threshold or class not established")
    if contradictory:
        review_reasons.append("Conflicting evidence")
    if extraction_incomplete:
        review_reasons.append(f"Extraction status is {extraction_status or 'unknown'}")
    if path_only:
        review_required = True
        review_reasons.append("Class suggested from folder path only")
    if review_required and (extraction_incomplete or content_class is None):
        # Unclassified or partially read documents never get a business destination.
        destination = "Intake / Exception Review"
    return {
        "sourceItemId": record.get("sourceItemId"),
        "driveId": record.get("driveId"),
        "siteId": record.get("siteId"),
        "sourcePath": record.get("sourcePath"),
        "filename": record.get("filename"),
        "classificationEngineVersion": ENGINE_VERSION,
        "classificationRuleVersion": rules.get("ruleVersion") or rules.get("version"),
        "classificationTimestamp": datetime.now(timezone.utc).isoformat(),
        "contentClass": content_class,
        "contentClassCandidate": best["targetClass"] if best else fallback["targetClass"],
        "contentTopic": topic_class,
        "contentTopicScore": topic["score"] if topic else None,
        "contentTopicRule": topic["ruleId"] if topic else ("PATH-HINT" if topic_source == "path" else None),
        "contentTopicSource": topic_source,
        "contentClassConfidenceScore": score,
        "contentClassConfidenceBand": band,
        "businessFunction": business_function or "Unknown",
        "businessFunctionConfidence": score if business_function_source == "rule" else min(score, 60) if business_function else 0,
        "businessFunctionSource": business_function_source,
        "pathClassHint": class_hint["classHint"] if class_hint else None,
        "pathClassOnly": path_only,
        "pathFolders": path_info.get("folders", []),
        "pathSignals": list({(item["signal"], item["value"], item["match"]): {key: item[key] for key in ("signal", "value", "match")} for item in path_info.get("signals", [])}.values()),
        "pathTags": path_info["tags"],
        "pathTagsMerged": None,
        "alternatePaths": [],
        "sensitivity": "General",
        "sensitivitySource": "Human Reviewed",
        "proposedDestination": destination,
        "routingEligibility": "REVIEW_REQUIRED" if review_required else "RECOMMENDATION_ONLY",
        "classificationStatus": "Review Required" if review_required else "Machine Classified",
        "matchedRules": matched_rules,
        "pathCorroborated": bool(best and best.get("pathCorroborated") and band == "HIGH"),
        "evidence": positive,
        "contradictoryEvidence": contradictory,
        "humanReviewRequired": review_required,
        "reviewReason": "; ".join(review_reasons) if review_required else None,
        "attributeExtractionReference": record.get("artifactReference"),
        "extractionStatus": extraction_status,
        "processingFailure": extraction_status in ("FAILED", "DOCUMENT_CHANGED", "UNSUPPORTED"),
        "extractionProcessingStatus": record.get("processingStatus"),
        "extractionSkipReason": record.get("skipReason"),
        "isDuplicateContent": False,
        "duplicateGroupId": None,
        "duplicateOfSourceItemId": None,
        "duplicateCount": 1,
        "duplicateMatchType": None,
        "duplicateDetectionStatus": "NOT_AVAILABLE" if not record.get("contentHash") else "NO_EXACT_DUPLICATE",
        "duplicateReviewRequired": False,
    }


def run_classification(extraction_aggregate, rules, expected_population=100):
    """Classify one immutable pilot population.

    expected_population is the manifest size (100 or 500). The check stays exact: one result per
    unique manifest item, no more and no fewer.
    """
    expected_population = int(expected_population)
    if expected_population < 1:
        raise ValueError("expected_population must be a positive manifest size.")
    extraction_records = extraction_aggregate.get("results", [])
    results = [classify_document(item, rules) for item in extraction_records]
    by_id = [result.get("sourceItemId") for result in results]
    if len(results) != expected_population or len(set(by_id)) != expected_population:
        raise ValueError(
            f"Classification requires exactly one result per unique manifest item ({expected_population} expected)."
        )
    if any(result.get("sensitivity") != "General" for result in results):
        raise ValueError(f"Sensitivity invariant failed; expected General for all {expected_population} documents.")
    by_hash = {}
    for record in extraction_records:
        content_hash = record.get("contentHash")
        if content_hash:
            by_hash.setdefault(content_hash, []).append(record["sourceItemId"])
    result_by_id = {result["sourceItemId"]: result for result in results}
    for content_hash, source_ids in by_hash.items():
        unique_ids = sorted(set(source_ids))
        if len(unique_ids) < 2:
            continue
        group_id = hashlib.sha256("\0".join(unique_ids).encode("utf-8")).hexdigest()[:20]
        canonical_id = unique_ids[0]
        merged = merge_path_context(result_by_id[source_id] for source_id in unique_ids)
        for source_id in unique_ids:
            result = result_by_id[source_id]
            result.update(
                {
                    "isDuplicateContent": True,
                    "duplicateGroupId": group_id,
                    "duplicateOfSourceItemId": canonical_id if source_id != canonical_id else None,
                    "duplicateCount": len(unique_ids),
                    "duplicateMatchType": "ExactContentHash",
                    "duplicateDetectionStatus": "EXACT_MATCH_REVIEW",
                    "duplicateReviewRequired": True,
                    "humanReviewRequired": True,
                    "classificationStatus": "Review Required",
                    "routingEligibility": "REVIEW_REQUIRED",
                    "proposedDestination": "Intake / Exception Review",
                    "pathTagsMerged": merged["pathTags"],
                    "alternatePaths": [path for path in merged["paths"] if path != result.get("sourcePath")],
                }
            )
            reason = "Exact content duplicate group; confirm duplicate handling"
            existing_reason = result.get("reviewReason")
            result["reviewReason"] = f"{existing_reason}; {reason}" if existing_reason else reason
    return {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "classificationEngineVersion": ENGINE_VERSION,
        "classificationRuleVersion": rules.get("ruleVersion") or rules.get("version"),
        "authorizedPopulation": expected_population,
        "extractionScanId": extraction_aggregate.get("scanId"),
        "results": results,
        "sourceMutations": 0,
        "sensitivityChanges": 0,
        "filesMoved": 0,
    }


def summarize_results(aggregate):
    results = aggregate["results"]
    classes = Counter(result["contentClass"] or "Unknown" for result in results)
    business = Counter(result["businessFunction"] for result in results)
    destinations = Counter(result["proposedDestination"] for result in results)
    bands = Counter(result["contentClassConfidenceBand"] for result in results)
    rules = Counter(rule for result in results for rule in result["matchedRules"])
    statuses = Counter(result["classificationStatus"] for result in results)
    attributes = Counter(
        evidence.get("signal")
        for result in results
        for evidence in (result.get("evidence", []) + result.get("contradictoryEvidence", []))
        if evidence.get("signal")
    )
    duplicate_groups = {result["duplicateGroupId"] for result in results if result.get("duplicateGroupId")}
    extraction_skips = Counter(
        result.get("extractionSkipReason") or "SKIPPED"
        for result in results
        if result.get("extractionProcessingStatus") == "SKIPPED"
    )
    path_tags = [result.get("pathTags") or {} for result in results]
    path_summary = {
        "withRetailer": sum(bool(tags.get("retailers")) for tags in path_tags),
        "withProduct": sum(bool(tags.get("products")) for tags in path_tags),
        "withBrand": sum(bool(tags.get("brands")) for tags in path_tags),
        "withPartner": sum(bool(tags.get("partners")) for tags in path_tags),
        "withPeriodYear": sum(bool(tags.get("periodYear")) for tags in path_tags),
        "withLifecycle": sum(bool(tags.get("lifecycle")) for tags in path_tags),
        "withAnyTag": sum(any(tags.get(key) for key in ("retailers", "products", "brands", "partners", "periodYear")) for tags in path_tags),
        "pathSupportedClass": sum(any(e.get("source") == "path" for e in result.get("evidence", [])) and not result.get("pathClassOnly") for result in results),
        "pathOnlyClass": sum(bool(result.get("pathClassOnly")) for result in results),
        "businessFunctionFromPath": sum(result.get("businessFunctionSource") == "path" for result in results),
        "topicFromPath": sum(result.get("contentTopicSource") == "path" for result in results),
        "retailers": dict(Counter(v for tags in path_tags for v in tags.get("retailers") or [])),
        "products": dict(Counter(v for tags in path_tags for v in tags.get("products") or [])),
        "brands": dict(Counter(v for tags in path_tags for v in tags.get("brands") or [])),
        "partners": dict(Counter(v for tags in path_tags for v in tags.get("partners") or [])),
        "periodYears": dict(Counter(str(tags.get("periodYear")) for tags in path_tags if tags.get("periodYear"))),
        "lifecycle": dict(Counter(v for tags in path_tags for v in tags.get("lifecycle") or [])),
    }
    competing = Counter(
        f"{result.get('contentClassCandidate')} vs {evidence.get('value')}"
        for result in results
        for evidence in result.get("contradictoryEvidence", [])
        if evidence.get("signal") == "competingRule"
    )
    path_summary["pathCorroboratedHigh"] = sum(bool(result.get("pathCorroborated")) for result in results)
    return {"competingRulePairs": dict(competing.most_common()), "pathEvidence": path_summary, "total": len(results), "classified": sum(result.get("contentClass") is not None for result in results), "confidenceBands": dict(bands), "reviewRequired": sum(item["humanReviewRequired"] for item in results), "processingFailures": sum(item["processingFailure"] for item in results), "extractionSkips": dict(extraction_skips), "duplicateDocuments": sum(result.get("isDuplicateContent", False) for result in results), "duplicateGroups": len(duplicate_groups), "duplicateReviewRequired": sum(result.get("duplicateReviewRequired", False) for result in results), "unknownOther": classes.get("Unknown", 0) + classes.get("Other", 0), "contentClassDistribution": dict(classes), "businessFunctionDistribution": dict(business), "proposedRoutingDistribution": dict(destinations), "ruleFrequency": dict(rules), "attributeEvidenceFrequency": dict(attributes), "classificationStatusDistribution": dict(statuses)}


def build_markdown_report(aggregate):
    summary = summarize_results(aggregate)
    population = aggregate.get("authorizedPopulation") or summary["total"]
    lines = [
        f"# Classification Pilot {population} Results",
        "",
        f"- Documents accounted for: {summary['total']}/{population}",
        f"- Classified: {summary['classified']}",
        f"- HIGH / MEDIUM / LOW: {summary['confidenceBands'].get('HIGH', 0)} / {summary['confidenceBands'].get('MEDIUM', 0)} / {summary['confidenceBands'].get('LOW', 0)}",
        f"- Review required: {summary['reviewRequired']}",
        f"- Unknown/Other: {summary['unknownOther']}",
        f"- Processing failures: {summary['processingFailures']}",
        f"- Extraction skips: {sum(summary['extractionSkips'].values())}",
        f"- Exact duplicate groups / documents flagged: {summary['duplicateGroups']} / {summary['duplicateDocuments']}",
        f"- Sensitivity: General for all {population} (Human Reviewed)",
        "- Files moved: 0; source mutations: 0",
        "",
    ]
    for title, key in (("ContentClass", "contentClassDistribution"), ("BusinessFunction", "businessFunctionDistribution"), ("Proposed routing", "proposedRoutingDistribution"), ("Confidence bands", "confidenceBands"), ("Rules fired", "ruleFrequency"), ("Attribute evidence frequency", "attributeEvidenceFrequency")):
        lines.extend((f"## {title}", "", "| Value | Count |", "|---|---:|"))
        lines.extend(f"| {name} | {count} |" for name, count in sorted(summary[key].items()))
        lines.append("")
    path = summary["pathEvidence"]
    if any(path[key] for key in ("withAnyTag", "withLifecycle", "pathSupportedClass", "pathOnlyClass")):
        lines.extend(("## Path Evidence", "",
                      f"- Documents with any path tag (retailer, product, brand, partner or year): {path['withAnyTag']}",
                      f"- Retailer / product / brand / partner / year: {path['withRetailer']} / {path['withProduct']} / {path['withBrand']} / {path['withPartner']} / {path['withPeriodYear']}",
                      f"- Lifecycle tag (draft, close-out, sync conflict, ...): {path['withLifecycle']}",
                      f"- Class supported by folder evidence: {path['pathSupportedClass']}",
                      f"- Class suggested from folder only (always review): {path['pathOnlyClass']}",
                      f"- BusinessFunction filled from folder: {path['businessFunctionFromPath']}",
                      f"- ContentTopic filled from folder: {path['topicFromPath']}", ""))
        for title, key in (("Path retailers", "retailers"), ("Path products", "products"), ("Path brands", "brands"), ("Path partners", "partners"), ("Path period year", "periodYears"), ("Path lifecycle", "lifecycle")):
            if path[key]:
                lines.extend((f"### {title}", "", "| Value | Count |", "|---|---:|"))
                lines.extend(f"| {name} | {count} |" for name, count in sorted(path[key].items(), key=lambda item: (-item[1], item[0])))
                lines.append("")
    lines.extend(("## Exceptions", "", "| Source item | File | Candidate | Score | Reason |", "|---|---|---|---:|---|"))
    for result in aggregate["results"]:
        if result["humanReviewRequired"]:
            lines.append(f"| {result['sourceItemId']} | {result['filename']} | {result['contentClassCandidate']} | {result['contentClassConfidenceScore']} | {result['reviewReason'] or 'Review required'} |")
    lines.extend(("", "## Exact Duplicate Groups", "", "| Group | Source item | Duplicate of | Filename |", "|---|---|---|---|"))
    for result in aggregate["results"]:
        if result.get("isDuplicateContent"):
            lines.append(f"| {result['duplicateGroupId']} | {result['sourceItemId']} | {result['duplicateOfSourceItemId'] or '(canonical)'} | {result['filename']} |")
    return "\n".join(lines) + "\n"


def _workbook_path_columns(result):
    tags = result.get("pathTagsMerged") or result.get("pathTags") or {}
    joined = lambda values: ", ".join(values or []) or None
    return [joined(tags.get("retailers")), joined(tags.get("products")), joined(tags.get("brands")), joined(tags.get("partners")),
            tags.get("periodYear"), joined(tags.get("lifecycle")), result.get("pathClassHint"),
            joined(f"{item['signal']}={item['value']}" for item in result.get("pathSignals") or []),
            "\n".join(result.get("alternatePaths") or []) or None]


def build_review_workbook(aggregate, output_path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Classification Review"
    headers = ["#", "Filename", "Source Path", "Sensitivity", "Proposed ContentClass", "Score", "Confidence", "BusinessFunction", "Proposed Destination", "Matched Rule", "Primary Evidence", "Contradictory Evidence", "Exact Duplicate", "Duplicate Group", "Duplicate Of Source Item", "Extraction Status", "Skip Reason", "Human Review Required", "Reviewer ContentClass", "Reviewer BusinessFunction", "Reviewer Destination", "Reviewer Change", "Reviewer Notes", "Final Status", "Content Topic", "Content Topic Source", "Retailers", "Products", "Brands", "Partners", "Period Year", "Lifecycle", "Path Class Hint", "Path Signals", "Alternate Paths"]
    sheet.append(headers)
    for number, result in enumerate(aggregate["results"], start=1):
        sheet.append([number, result["filename"], result["sourcePath"], "General", result["contentClassCandidate"], result["contentClassConfidenceScore"], result["contentClassConfidenceBand"], result["businessFunction"], result["proposedDestination"], ", ".join(result["matchedRules"]), json.dumps(result["evidence"], ensure_ascii=False), json.dumps(result["contradictoryEvidence"], ensure_ascii=False), result["isDuplicateContent"], result["duplicateGroupId"], result["duplicateOfSourceItemId"], result["extractionStatus"], result["extractionSkipReason"], result["humanReviewRequired"], None, None, None, None, None, result["classificationStatus"], result.get("contentTopic"), result.get("contentTopicSource"), *_workbook_path_columns(result)])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="244A5A")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    widths = [6, 38, 72, 14, 24, 10, 12, 20, 32, 18, 54, 38, 16, 24, 32, 20, 36, 22, 24, 24, 30, 18, 38, 22, 24]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (11, 12))
    workbook.save(output_path)