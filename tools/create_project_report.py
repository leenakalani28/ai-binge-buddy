"""Generate a shareable Word report using standard-library OOXML only."""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "AI Binge Buddy - Final Project Report.docx"

sections = [
    ("Title", "AI Binge Buddy"),
    ("Subtitle", "Final project report | 11 October 2026"),
    ("Heading1", "1. Project overview"),
    (None, "A Streamlit AI assistant that helps 1-6 people choose a movie, TV series or documentary. Users select content type, genre, original language and streaming platform. The app offers up to three real recommendations, personalised explanations, an optional friendly roast, a poster-filled decision wheel and a winner celebration."),
    (None, "Built using Python, Streamlit, HTTPX, Pydantic and uv. OpenAI gpt-oss-120b, accessed through Groq, makes the recommendation decisions. Python checks eligibility and validates the response; it no longer provides fallback recommendations."),
    ("Heading1", "2. Data sources"),
    (None, "TMDB provides live titles, genres, languages, posters, ratings, runtimes, credits and trailers. JustWatch data through TMDB provides regional streaming, rent and buy options. Users supply names and four preferences; relevant information is sent to Groq. No custom training dataset or model training was used."),
    ("Heading1", "3. Prompts used"),
    (None, "The initial master prompt requested a working Streamlit app with TMDB, Groq, group recommendations, a roast, a random wheel, tests and uv setup. Follow-up prompts included:"),
    (None, '"The UI is not at all user friendly. It looks very basic, unreadable and slow. Can you make it professional."'),
    (None, '"I want each triangle to be filled with the corresponding poster."'),
    (None, '"the preference page takes time to load and takes time to load the forms"'),
    (None, '"do not use python as fallback if LLM is not responding. instead just show me the error message on screen"'),
    (None, "The final AI prompt grounds selection in supplied TMDB data: choose exactly the required number of distinct candidate IDs, balance everyone’s tastes, explain individual fit and compromises, follow the JSON structure, and never invent titles, availability or match percentages. Python checks whether those instructions were followed."),
    ("Heading1", "4. Iterations tried"),
    (None, "Moved from Python scoring to LLM-led selection of eligible TMDB candidates. Simplified preferences to four fields. Redesigned setup screens, enlarged fonts, separated AI commentary, added poster-filled wheel sectors and a winner celebration. Fixed stacked-screen navigation and wheel scroll handling. Added a faint poster-collage background while keeping form panels opaque for readability."),
    (None, "Improved responsiveness with batched forms, parallel API requests, reused connections and a 24-hour preference catalogue cache. Fetches detail for 48 titles initially, expanding to up to 120 if fewer than three qualify. Oversized Groq requests are compacted; if still rejected, the LLM evaluates smaller batches and selects finalists. API/model failures now show an error and Retry button, without substitute recommendations."),
    ("Heading1", "5. Learnings and observations"),
    (None, "Specific prompts and screenshots made iterative improvements easier. The LLM is useful for subjective decisions, while external facts, grounding prompts and Python validation make outputs more dependable. Prompt instructions alone do not guarantee correctness. Larger candidate lists increase request size, latency and rate-limit risk; caching and compact data help. API keys stay in an ignored .env file."),
    (None, "Verification: 23 regression tests passed after the final background changes. A separate offline audit passed 25 button/action cases and six configured external-link checks; wheel outcomes and the scroll guard also passed. API responses were mocked. Actual browser scroll positions and external pages were not verified, and no performance benchmark was recorded."),
]

def paragraph(style, text):
    properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{properties}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document {ns}><w:body>{''.join(paragraph(*item) for item in sections)}
<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="850" w:right="1000" w:bottom="850" w:left="1000"/></w:sectPr>
</w:body></w:document>'''
styles = f'''<?xml version="1.0" encoding="UTF-8"?><w:styles {ns}>
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="21"/><w:color w:val="283345"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="260" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:keepNext/><w:spacing w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="48"/><w:color w:val="173B53"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:keepNext/><w:spacing w:after="230"/></w:pPr><w:rPr><w:sz w:val="21"/><w:color w:val="667085"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="170" w:after="90"/></w:pPr><w:rPr><w:b/><w:sz w:val="27"/><w:color w:val="173B53"/></w:rPr></w:style>
</w:styles>'''
parts = {
    "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
    "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    "word/document.xml": document,
    "word/styles.xml": styles,
    "word/_rels/document.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
}
for content in parts.values():
    ElementTree.fromstring(content)
with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
    for name, content in parts.items():
        archive.writestr(name, content.encode("utf-8"))
with ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
print(f"Created: {OUTPUT.name}")
