"""
Algorithmic SEO scorer -- no AI call, instant feedback.
Scores 10 criteria against industry best-practice thresholds.
Returns a 0-100 total, a letter grade, and a per-check breakdown.
"""
import re
from dataclasses import dataclass, field


@dataclass
class SEOCheck:
    name: str
    score: int
    max_score: int
    status: str   # "pass" | "warn" | "fail"
    tip: str


@dataclass
class SEOScore:
    total: int
    grade: str
    checks: list[SEOCheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "grade": self.grade,
            "checks": [
                {
                    "name": c.name,
                    "score": c.score,
                    "max_score": c.max_score,
                    "status": c.status,
                    "tip": c.tip,
                }
                for c in self.checks
            ],
        }


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip().split()) > 2]


class SEOScorer:

    def score(
        self,
        headline: str,
        meta_title: str,
        meta_description: str,
        focus_keyword: str,
        secondary_keywords: list[str],
        article_html: str,
        word_count: int,
    ) -> SEOScore:

        plain_text = _strip_html(article_html)
        kw = focus_keyword.lower().strip()
        text_lower = plain_text.lower()

        first_p = re.search(r"<p[^>]*>(.*?)</p>", article_html, re.IGNORECASE | re.DOTALL)
        first_p_text = _strip_html(first_p.group(1)).lower() if first_p else ""

        p_count  = len(re.findall(r"<p[^>]*>",  article_html, re.IGNORECASE))
        h2_count = len(re.findall(r"<h2[^>]*>", article_html, re.IGNORECASE))

        checks: list[SEOCheck] = []

        # 1. Focus keyword in meta title (15 pts)
        if not kw:
            checks.append(SEOCheck("Keyword in Title", 0, 15, "fail",
                "No focus keyword set. Add one in the SEO metadata."))
        elif kw in meta_title.lower():
            checks.append(SEOCheck("Keyword in Title", 15, 15, "pass",
                "Focus keyword found in meta title."))
        else:
            checks.append(SEOCheck("Keyword in Title", 0, 15, "fail",
                f'Add "{focus_keyword}" to the meta title.'))

        # 2. Focus keyword in first paragraph (10 pts)
        if not kw:
            checks.append(SEOCheck("Keyword in Opening", 0, 10, "fail",
                "Set a focus keyword first."))
        elif kw in first_p_text:
            checks.append(SEOCheck("Keyword in Opening", 10, 10, "pass",
                "Focus keyword appears early in the article."))
        else:
            checks.append(SEOCheck("Keyword in Opening", 0, 10, "fail",
                f'Mention "{focus_keyword}" in the opening paragraph.'))

        # 3. Keyword density 0.5-3% (10 pts)
        if kw and word_count > 0:
            occ = text_lower.count(kw)
            density = (occ / word_count) * 100
            if 0.5 <= density <= 3.0:
                pts, st, tip = 10, "pass", f"Keyword density {density:.1f}% — ideal."
            elif density < 0.5:
                pts, st, tip = 5, "warn", f"Density {density:.1f}% — use the keyword more often."
            else:
                pts, st, tip = 3, "warn", f"Density {density:.1f}% — reduce keyword stuffing (max 3%)."
        else:
            pts, st, tip = 0, "fail", "No focus keyword set."
        checks.append(SEOCheck("Keyword Density", pts, 10, st, tip))

        # 4. Meta title length 50-60 chars (10 pts)
        mt_len = len(meta_title)
        if 50 <= mt_len <= 60:
            pts, st, tip = 10, "pass", f"Meta title {mt_len} chars — perfect."
        elif 40 <= mt_len < 50 or 60 < mt_len <= 70:
            pts, st, tip = 6, "warn", f"Meta title {mt_len} chars — ideal is 50-60."
        elif mt_len < 40:
            pts, st, tip = 2, "fail", f"Meta title too short ({mt_len} chars). Aim for 50-60."
        else:
            pts, st, tip = 2, "fail", f"Meta title too long ({mt_len} chars). Keep under 60."
        checks.append(SEOCheck("Meta Title Length", pts, 10, st, tip))

        # 5. Meta description length 140-155 chars (10 pts)
        md_len = len(meta_description)
        if 140 <= md_len <= 155:
            pts, st, tip = 10, "pass", f"Meta description {md_len} chars — perfect."
        elif 120 <= md_len < 140 or 155 < md_len <= 165:
            pts, st, tip = 6, "warn", f"Meta description {md_len} chars — aim for 140-155."
        elif md_len < 120:
            pts, st, tip = 2, "fail", f"Meta description too short ({md_len} chars). Aim for 140-155."
        else:
            pts, st, tip = 2, "fail", f"Meta description too long ({md_len} chars). Trim to under 155."
        checks.append(SEOCheck("Meta Description Length", pts, 10, st, tip))

        # 6. Word count >= 700 (10 pts)
        if word_count >= 700:
            pts, st, tip = 10, "pass", f"{word_count} words — good length for SEO."
        elif word_count >= 500:
            pts, st, tip = 7, "warn", f"{word_count} words — aim for 700+ for better ranking."
        elif word_count >= 300:
            pts, st, tip = 4, "warn", f"{word_count} words — too short; expand to 700+."
        else:
            pts, st, tip = 0, "fail", f"Only {word_count} words — significantly below the SEO minimum."
        checks.append(SEOCheck("Word Count", pts, 10, st, tip))

        # 7. H2 subheadings >= 2 (10 pts)
        if h2_count >= 2:
            pts, st, tip = 10, "pass", f"{h2_count} subheadings — well structured."
        elif h2_count == 1:
            pts, st, tip = 5, "warn", "Only 1 subheading — add at least one more."
        else:
            pts, st, tip = 0, "fail", "No <h2> subheadings found — add 2-3 section headings."
        checks.append(SEOCheck("Subheadings (H2)", pts, 10, st, tip))

        # 8. Secondary keywords in body (10 pts) — 3 pts each, max 10
        if secondary_keywords:
            found = sum(1 for kw2 in secondary_keywords if kw2.lower() in text_lower)
            pts = min(10, found * 3)
            if found >= 3:
                st, tip = "pass", f"{found}/{len(secondary_keywords)} secondary keywords present."
            elif found >= 1:
                st, tip = "warn", f"{found}/{len(secondary_keywords)} secondary keywords — add more."
            else:
                st, tip = "fail", "None of the secondary keywords appear in the article body."
        else:
            pts, st, tip = 0, "fail", "No secondary keywords set."
        checks.append(SEOCheck("Secondary Keywords", pts, 10, st, tip))

        # 9. Readability — avg sentence length <= 18 words (10 pts)
        sentences = _sentences(plain_text)
        if sentences:
            avg = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg <= 18:
                pts, st, tip = 10, "pass", f"Avg sentence {avg:.0f} words — easy to read."
            elif avg <= 23:
                pts, st, tip = 6, "warn", f"Avg sentence {avg:.0f} words — slightly long."
            else:
                pts, st, tip = 3, "fail", f"Avg sentence {avg:.0f} words — too long for readability."
        else:
            pts, st, tip = 0, "fail", "Could not analyse sentence length."
        checks.append(SEOCheck("Readability", pts, 10, st, tip))

        # 10. Paragraph structure >= 4 (5 pts)
        if p_count >= 4:
            pts, st, tip = 5, "pass", f"{p_count} paragraphs — good structure."
        elif p_count >= 2:
            pts, st, tip = 3, "warn", f"Only {p_count} paragraphs — aim for 4+."
        else:
            pts, st, tip = 0, "fail", "Very few paragraphs — add more structure."
        checks.append(SEOCheck("Paragraph Structure", pts, 5, st, tip))

        total = sum(c.score for c in checks)
        grade = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D" if total >= 35 else "F"

        return SEOScore(total=total, grade=grade, checks=checks)
