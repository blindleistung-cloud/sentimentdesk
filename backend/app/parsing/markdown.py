from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.config.settings import Settings
from app.schemas.report import (
    CapexItem,
    EvidenceMatch,
    IndexMove,
    LayerAValuation,
    LayerBCapex,
    LayerCRisk,
    LayerDMarketContext,
    LayerInput,
    OvervaluedStock,
    RatioValue,
    RiskCluster,
)


IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_IMG_RE = re.compile(r"<img[^>]*>", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]:.*$", re.MULTILINE)
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")
SECTION_HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$")

STOCK_HEADER_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:\*{0,2})?(?:Platz\s*)?(\d+)[\.:\)]?\s*(?:\*{0,2})?(.+?)\s*(?:\(([^)]+)\))?\s*(?:[-\u2013\u2014]\s*(.*))?$",
    re.IGNORECASE,
)

AMOUNT_RE = re.compile(r"([0-9]{1,4}(?:[.,][0-9]+)?)\s*(?:mrd|milliarden|billion|bn|b)\b", re.IGNORECASE)
PERCENT_RE = re.compile(r"([0-9]{1,3}(?:[.,][0-9]+)?)\s*%")
YEAR_RE = re.compile(r"\b(20\d{2})\b")
NUMBER_RE = re.compile(r"([+-]?[0-9]+(?:[.,][0-9]+)?)")


@dataclass
class ParsedContent:
    cleaned_text: str
    layers: LayerInput
    evidence: list[EvidenceMatch]


def fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def clean_markdown(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n")
    text = HTML_IMG_RE.sub("", text)
    text = IMAGE_MD_RE.sub("", text)
    text = FOOTNOTE_DEF_RE.sub("", text)
    text = FOOTNOTE_REF_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = text.replace("−", "-")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "root"
    buffer: list[str] = []
    for line in text.splitlines():
        match = SECTION_HEADER_RE.match(line.strip())
        if match:
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
            current_heading = match.group(1).strip()
            buffer = []
            continue
        buffer.append(line)
    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))
    return sections


def parse_number(raw_value: str) -> float:
    cleaned = raw_value.replace("+", "").replace(",", ".")
    return float(cleaned)


def make_evidence(field: str, rule_id: str, pattern: str, snippet: str) -> EvidenceMatch:
    return EvidenceMatch(field=field, rule_id=rule_id, pattern=pattern, snippet=snippet.strip())


def find_section_text(sections: list[tuple[str, str]], keywords: list[str]) -> str:
    for heading, body in sections:
        head = heading.lower()
        head_fold = fold_text(heading)
        if any(keyword in head or keyword in head_fold for keyword in keywords):
            return f"{heading}\n{body}".strip()
    return ""


def extract_ratio(block_text: str, patterns: list[str], field: str) -> tuple[RatioValue | None, EvidenceMatch | None]:
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        match = regex.search(block_text)
        if match:
            number_match = NUMBER_RE.search(match.group(0))
            if not number_match:
                continue
            value = parse_number(number_match.group(1))
            evidence = make_evidence(field, f"ratio:{field}", pattern, match.group(0))
            return RatioValue(value=value, raw=match.group(0)), evidence
    return None, None


def extract_overvalued_stocks(section_text: str) -> tuple[list[OvervaluedStock], list[EvidenceMatch]]:
    stocks: list[OvervaluedStock] = []
    evidence: list[EvidenceMatch] = []
    if not section_text:
        return stocks, evidence

    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    blocks: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in lines:
        clean_line = line.replace("**", "").strip()
        match = STOCK_HEADER_RE.match(clean_line)
        if match:
            name = match.group(2).strip()
            name = re.split(r"\s*[-\u2013\u2014]\s*", name)[0].strip()
            if "die fünf" in name.lower():
                continue
            commentary = (match.group(4) or "").strip() or None
            if current:
                blocks.append(current)
            current = {
                "rank": int(match.group(1)),
                "name": name,
                "ticker": (match.group(3) or "").strip() or None,
                "commentary": commentary,
                "lines": [],
            }
            continue
        if current:
            current["lines"].append(line)
    if current:
        blocks.append(current)

    blocks = sorted(blocks, key=lambda item: item.get("rank", 999))
    blocks = blocks[:5]

    for block in blocks:
        block_text = "\n".join(block["lines"]) if block.get("lines") else ""
        line_commentary = " ".join(line.strip() for line in block.get("lines", []) if line.strip())
        commentary_parts = []
        if block.get("commentary"):
            commentary_parts.append(str(block["commentary"]))
        if line_commentary:
            commentary_parts.append(line_commentary)
        commentary = " ".join(commentary_parts).strip() or None
        pe_ratio, pe_evidence = extract_ratio(
            block_text,
            [r"\bKGV[^0-9]*[0-9]+", r"\bP\s*/\s*E[^0-9]*[0-9]+", r"price[- ]to[- ]earnings[^0-9]*[0-9]+"],
            "valuation.pe_ratio",
        )
        pb_ratio, pb_evidence = extract_ratio(
            block_text,
            [r"\bKBV[^0-9]*[0-9]+", r"\bP\s*/\s*B[^0-9]*[0-9]+", r"price[- ]to[- ]book[^0-9]*[0-9]+"],
            "valuation.pb_ratio",
        )
        pcf_ratio, pcf_evidence = extract_ratio(
            block_text,
            [r"\bKCV[^0-9]*[0-9]+", r"\bP\s*/\s*CF[^0-9]*[0-9]+", r"price[- ]to[- ]cash[- ]flow[^0-9]*[0-9]+"],
            "valuation.pcf_ratio",
        )

        item_evidence = [ev for ev in [pe_evidence, pb_evidence, pcf_evidence] if ev]
        evidence.extend(item_evidence)
        stocks.append(
            OvervaluedStock(
                rank=block["rank"],
                name=block["name"],
                ticker=block["ticker"],
                commentary=commentary,
                pe_ratio=pe_ratio,
                pb_ratio=pb_ratio,
                pcf_ratio=pcf_ratio,
                evidence=item_evidence,
            )
        )

    return stocks, evidence


def extract_stock_mentions(
    cleaned_text: str, stocks: list[OvervaluedStock]
) -> dict[str, list[str]]:
    mentions: dict[str, list[str]] = {}
    targets: list[tuple[str, str]] = []

    for stock in stocks:
        ticker = (stock.ticker or "").strip().upper()
        name = stock.name.strip()
        if not ticker or not name:
            continue
        mentions[ticker] = []
        targets.append((ticker, fold_text(name)))

    if not targets:
        return mentions

    for raw_line in cleaned_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if STOCK_HEADER_RE.match(line):
            continue
        line_fold = fold_text(line)
        for ticker, name_fold in targets:
            if re.search(rf"\b{re.escape(ticker)}\b", line, re.IGNORECASE):
                if line not in mentions[ticker]:
                    mentions[ticker].append(line)
                continue
            if name_fold and name_fold in line_fold:
                if line not in mentions[ticker]:
                    mentions[ticker].append(line)

    return mentions


def extract_capex(section_text: str) -> tuple[LayerBCapex, list[EvidenceMatch]]:
    evidence: list[EvidenceMatch] = []
    if not section_text:
        return LayerBCapex(), evidence

    known_companies = [
        "Amazon",
        "Microsoft",
        "Google",
        "Meta",
        "Oracle",
        "Alphabet",
        "Apple",
        "Nvidia",
        "Tesla",
        "Palantir",
        "Broadcom",
    ]

    capex_items: list[CapexItem] = []
    capex_total: float | None = None
    ai_share: float | None = None

    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        amount_match = AMOUNT_RE.search(line)
        if not amount_match:
            continue
        amount = parse_number(amount_match.group(1))
        year_match = YEAR_RE.search(line)
        year = int(year_match.group(1)) if year_match else None

        company = None
        for name in known_companies:
            if name.lower() in line.lower():
                company = name
                break

        if company:
            item_evidence = [
                make_evidence("capex.item", "capex:amount", AMOUNT_RE.pattern, amount_match.group(0))
            ]
            evidence.extend(item_evidence)
            capex_items.append(
                CapexItem(
                    company=company,
                    year=year,
                    amount_usd_billion=amount,
                    evidence=item_evidence,
                )
            )
            continue

        if any(keyword in line.lower() for keyword in ["aggreg", "gesamt", "total", "insgesamt"]):
            capex_total = amount
            evidence.append(
                make_evidence("capex.total", "capex:total", AMOUNT_RE.pattern, amount_match.group(0))
            )

        if "ai" in line.lower():
            percent_match = PERCENT_RE.search(line)
            if percent_match:
                ai_share = parse_number(percent_match.group(1))
                evidence.append(
                    make_evidence("capex.ai_share", "capex:ai_share", PERCENT_RE.pattern, percent_match.group(0))
                )

    return LayerBCapex(
        capex_items=capex_items,
        capex_total_usd_billion=capex_total,
        ai_share_percent=ai_share,
    ), evidence


def extract_risk_clusters(cleaned_text: str, settings: Settings) -> tuple[LayerCRisk, list[EvidenceMatch]]:
    evidence: list[EvidenceMatch] = []
    clusters: list[RiskCluster] = []
    lower = cleaned_text.lower()
    folded = fold_text(cleaned_text)

    for label, keywords in settings.parser.risk_keywords.items():
        count = 0
        snippet = None
        for keyword in keywords:
            matches = list(re.finditer(re.escape(keyword), folded))
            count += len(matches)
            if matches and snippet is None:
                start = max(matches[0].start() - 40, 0)
                end = min(matches[0].end() + 40, len(folded))
                snippet = cleaned_text[start:end]
        if count > 0:
            item_evidence: list[EvidenceMatch] = []
            if snippet:
                item_evidence.append(
                    make_evidence("risk.cluster", f"risk:{label}", "|".join(keywords), snippet)
                )
            evidence.extend(item_evidence)
            clusters.append(RiskCluster(label=label, count=count, evidence=item_evidence))

    return LayerCRisk(risk_clusters=clusters), evidence


def extract_market_context(cleaned_text: str, settings: Settings) -> tuple[LayerDMarketContext, list[EvidenceMatch]]:
    evidence: list[EvidenceMatch] = []
    week_label = None

    week_match = re.search(r"(KW\s*\d+\s*/\s*\d{4}|Woche\s+[0-9]{1,2}\s*[-\u2013]\s*[0-9]{1,2}\s+\w+\s+\d{4})", cleaned_text)
    if week_match:
        week_label = week_match.group(1)
        evidence.append(make_evidence("market_context.week", "market:week", week_match.re.pattern, week_label))

    index_moves: list[IndexMove] = []
    for index_name in settings.parser.index_names:
        regex = re.compile(rf"{re.escape(index_name)}[^\n%]*([+-]?[0-9]+(?:[.,][0-9]+)?)\s*%", re.IGNORECASE)
        match = regex.search(cleaned_text)
        if not match:
            continue
        percent = parse_number(match.group(1))
        direction = "flat"
        if percent > 0:
            direction = "up"
        elif percent < 0:
            direction = "down"
        item_evidence = [
            make_evidence("market_context.index", "market:index_move", regex.pattern, match.group(0))
        ]
        evidence.extend(item_evidence)
        index_moves.append(
            IndexMove(
                index=index_name,
                percent_change=percent,
                direction=direction,
                evidence=item_evidence,
            )
        )

    return LayerDMarketContext(week_label=week_label, index_moves=index_moves), evidence


def parse_report(raw_text: str, settings: Settings) -> ParsedContent:
    cleaned_text = clean_markdown(raw_text)
    sections = split_sections(cleaned_text)

    valuation_text = find_section_text(sections, ["uberwert", "ubergewicht", "overvalu", "bewert"])
    capex_text = find_section_text(sections, ["capex"])

    valuation_items, valuation_evidence = extract_overvalued_stocks(valuation_text or cleaned_text)
    capex_layer, capex_evidence = extract_capex(capex_text or cleaned_text)
    risk_layer, risk_evidence = extract_risk_clusters(cleaned_text, settings)
    market_layer, market_evidence = extract_market_context(cleaned_text, settings)

    layers = LayerInput(
        valuation=LayerAValuation(overvalued_stocks=valuation_items),
        capex=capex_layer,
        risk=risk_layer,
        market_context=market_layer,
    )

    evidence = []
    evidence.extend(valuation_evidence)
    evidence.extend(capex_evidence)
    evidence.extend(risk_evidence)
    evidence.extend(market_evidence)

    return ParsedContent(cleaned_text=cleaned_text, layers=layers, evidence=evidence)
