# Retrieval Discipline — The Source Ladder & the Authenticity Gate

*Read by the gatherers (`gatherer-canon`, `gatherer-voices`) and the gather orchestrator. The doctrine of getting **real** primary text into a corpus — and never letting a failed fetch become invented text.*

## The Absolute Rule

**A failed fetch never falls through to generation.** If you cannot retrieve a source, you say so and leave its `content` empty with a failure flag (see the content-bearing clause in `agent-preamble.md`). You do **not** reconstruct it from memory, paraphrase it as if quoted, or fill in what the text "probably says."

A facet built on invented source text points an LLM at a hallucination wearing the lineage's name—and it is the one failure that corrupts everything downstream *while passing every structural check* (valid JSON, content present, plausible length). Fabrication is the only unrecoverable error in this pipeline. Everything else—a thin corpus, a locked author, a partial load—is honest and survivable. When in doubt, under-claim and flag.

## The Source Ladder

Climb in order; stop at the first rung that yields **authentic, verifiable** text (see the gate below). Born-digital plain text beats OCR beats scraped HTML. Lower rungs are more effortful or lower-fidelity, not better.

1. **Gutendex** (`gutendex.com/books?search=...`) — Project Gutenberg index; serves **plain text + epub**. Best first stop for public-domain canon: clean, born-digital.
2. **Wikisource** (`*.wikisource.org/w/api.php?action=parse&page=...&prop=wikitext`) — transcribed primary texts; follow "versions"/disambiguation pages to the actual edition.
3. **Wikiquote** (`*.wikiquote.org/w/api.php`) — sourced, attributed **primary-voice quotation** when full texts are locked. The voice-gatherer's friend.
4. **arXiv** (`export.arxiv.org/api/query`) — living theory/technical lineages; author-deposited full-text PDFs.
5. **DOAJ** (`doaj.org/api/v4/search/articles/...`) — open-access scholarly articles.
6. **Semantic Scholar** (`api.semanticscholar.org`) — open-access PDFs + abstracts; good for tracing a lineage's citation spine.
7. **Open Library** (`openlibrary.org/search.json`) — bibliographic confirmation + a bridge to Internet Archive items.
8. **Internet Archive — metadata-gated** (the workhorse for 20th-century canon). Access is **per-scanned-item, never per-author**:
   - Query `archive.org/metadata/{id}`.
   - The item is openly readable as plain text **if**: a `{id}_djvu.txt` file is present, AND `access-restricted-item` is not `true`, AND `collection` contains neither `inlibrary` nor `printdisabled`.
   - Fetch the OCR: `archive.org/download/{id}/{id}_djvu.txt` (or `/stream/{id}/{id}_djvu.txt`).
   - **Chase single-volume scans, not the omnibus.** The *Complete/Collected* editions are the ones most often locked; the same author's individual collections frequently serve OCR freely. Search the specific collection title as its own item and test each.
9. **Hosted PDF / epub / mobi failover** — search `"<collection title>" pdf` (or `"<collection>" <author> pdf`). Freely-hosted documents on arbitrary domains (WordPress, `.edu` course folders, personal sites) bypass the fetch-layer copyright refusal that blocks recognized works.
   - `WebFetch` the PDF URL; if it returns no text, `curl -sL <url> -o f.pdf && pdftotext f.pdf -` (fallbacks: `pdfminer`/`PyPDF2` in python; `strings` last). 
   - **PoemHunter "Classic Poetry Series" *ebook PDFs*** (`poemhunter.com/<poet>/ebooks/?ebook=0&filename=...pdf`) are a high-yield single first-stop for poetry. Restored/critical editions are ideal—authoritative ordering + apparatus.
10. **`corpus/manual/`** — the human-provided escape hatch. For estate-locked anchors the fetch layer simply will not serve, this is the **only** route to their actual text: the user drops the file (with provenance) and the pipeline ingests it. The cleanest division of labor — the human supplies what the fetch layer won't.

**Avoid for body text:** HathiTrust/HTRC (access restricted; not a reliable programmatic source). Poetry Foundation, poets.org, and community poem-*display* pages (allpoetry, hellopoetry, poemhunter's poem pages)—the fetch layer 403s or copyright-refuses them. Use these only for *bibliographic confirmation* (which works exist), never as content.

## Formats: Prefer Text and Epub Over Scraped HTML

Where a source offers several formats, prefer **epub/mobi → text** (Gutendex, archive.org) over scraped HTML—cleaner, fewer navigation artifacts. Add an epub/mobi → plain-text step (`pandoc`, `ebook-convert`, or unzip-the-epub + strip tags). For PDFs, `pdftotext` first; expect OCR noise from scans (which is a *good* sign—see below). **And `WebFetch` is for essay-length pieces, not books**—its extraction layer silently summarizes long documents, so for any book-length canonical work skip `WebFetch` and pull the raw file (`curl -sL <url> -o f && …`), then verify bytes (the gate below). A born-digital plain-text book should land within a small margin of its raw `Content-Length`.

## The Authenticity Gate (before any source enters the corpus)

Every fetched body passes these before it counts as `content`. The gate exists because the worst failure—fabricated text reported as `success`—passes every *structural* check. These test **genuineness**, not structure.

- **Final-line anchor (primary tell).** Confirm the text ends where the real work ends—the actual last line, not a recurring mid-text phrase. (Trap: anchoring on a phrase that recurs truncates silently) Anchor on the *distinctive final variation*, not the first occurrence.
- **Reported-vs-written byte diff (the deterministic truncation tell).** Every anchor check above can pass on a *truncated* text: `WebFetch` runs an extraction layer that summarizes long pages, so it can return a book's opening **and** closing while silently dropping the middle. Anchors are necessary, not sufficient; only **bytes** see a missing middle. So for any work longer than a single essay, **independently probe the raw source size and diff it against what you wrote.** For born-digital plain text and `_djvu.txt`/`pdftotext` output (where raw bytes ≈ body chars) the probe is ground truth: `curl -sIL "$URL"` (read `Content-Length`) or `curl -sL "$URL" | wc -c`. If your written `content` is a small fraction of the raw bytes, you truncated — re-fetch via the raw-download path (rung 9), **never** `WebFetch`, and re-measure. Record `reported_bytes` and `written_chars` so the gather gate can see the diff. (For HTML, raw bytes include navigation chrome and the diff over-counts; there, fall back to expected-magnitude sanity—a "complete" canonical book under ~50 KB is a truncation until proven otherwise. A canon agent also over-claimed "10/10 full" three times before the disk agreed: verify the artifact, never the narration.)
- **Opening-line cross-check.** Verify the opening line against a second independent source (a bibliographic page, a quote DB). Mismatch = wrong edition, or invention.
- **OCR-artifact signature—presence is *proof of genuineness*.** Real scans carry artifacts ("W e" for "We", "bom" for "born", split words, stray page numbers). Their presence is positive evidence the text came from a real scan, not model memory. The inverse is the alarm: **clean, artifact-free text from an agent that reported it "couldn't fetch" the source is a hallucination red flag.** A real fetch is either clean-because-born-digital (then verify against known lines) or noisy-because-scanned (genuine). Clean text with *no* provenance and a failed-fetch story is fabricated until proven otherwise.
- **Refusal / HTML sniff.** Check the body isn't a copyright-refusal message, a login wall, a CAPTCHA page, or raw HTML chrome mistaken for content.

Failing the gate is **not** a license to fabricate. It is a signal to climb to the next rung, fail over to voice (below), or route to `corpus/manual/`.

## Reachability Is Binary and Estate-Determined — Not Effort-Bound

For estate-locked authors, going harder does not change a structural lock. An author is reachable in a genre **if** an open source serving full text exists; if every rung is locked.

**Findability = (author × genre × estate × archive)**, not a single yes/no. The same author is often **locked in one genre and open in another**—poems estate-locked, interviews and letters freely transcribed. So when a canon is locked, **lean harder on the voice-gatherer**: interviews, letters, talks, widely-quoted lines.

But interviews are **not a substitute for finished work.** A facet aims, at its best, to render an *epistemology*—a way of thinking—as far as that can be carried by voice; and finished work usually carries the worked-out epistemology more fully than off-the-cuff interview speech. So when an anchor's finished work is locked and only interviews or fragments remain, do **not** silently declare it sufficient. Surface it at the gather gate as a **human choice**: (a) accept the limitation and build from voice/fragments, (b) bring the work via `corpus/manual/`, or (c) drop this anchor. What coverage is good enough for *this* facet's aim is the human's call—the pipeline never makes it for them. Either way, surface the genre/estate asymmetry at the gate so the human sees the true coverage shape.

---

*The discipline in one line: climb the ladder, pass the gate, and when the text will not come, say so—never invent it.*