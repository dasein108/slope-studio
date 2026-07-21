"""Write candidate comments.

The only leverage is indirect: an interesting comment makes a reader click the
commenter's name. So the comment must never mention us. Self-promotion in
comments is the actual bannable line, and it also does not work.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from studio.config import default_provider
from studio.guerrilla import transcript as tr
from studio.guerrilla.highlight import Moment

STYLE_TAGS = ("provocative_question", "joke", "contrarian_take", "insight")
MAX_LEN = 280  # long comments get collapsed behind "Read more" and lose their pull

SYSTEM = """You write YouTube comments that make strangers curious enough to click the
commenter's name.

HARD RULES:
- NEVER mention yourself, your channel, your videos, or ask anyone to subscribe, follow, watch,
  or check anything out. No links. No handles. Breaking this rule makes the comment worthless.
- The comment must be unmistakably ABOUT THIS SPECIFIC VIDEO. Generic praise ("great video!",
  "underrated channel") is a failure. A reader must be unable to paste it under a different
  video and have it still fit.
- Sound like one specific person with a real opinion, not a brand. No emoji spam, no hashtags,
  no ALL CAPS, no engagement-bait phrasing ("who else...", "drop a like if...").
- Never insult the creator, the audience, or any group. Provocative means intellectually
  provocative — a claim someone would want to argue with, not an offensive one.
- Under 280 characters.

FORBIDDEN OPENERS — never start a comment with any of these constructions, in any phrasing:
"If ...," / "Isn't it interesting that ..." / "What if ..." / "Imagine if ...". These are the
single most common bot tell on YouTube: the same rhetorical mold repeated across videos, worded
differently but structurally identical, is what gets a channel's comments mass-flagged as spam
even when no individual comment repeats another word-for-word. Every variant must open on a
genuinely different sentence shape, not just different words plugged into the same shape.

THE OTHER TELL — the hedged-reviewer voice. Dodging "If..." tends to collapse straight into a
second template that reads just as bot-like: polite, hedged, and structured like a book-review
blurb. BANNED constructions, in any phrasing:
- "It's fascinating how ..."
- "... really challenges traditional/conventional views/understanding ..."
- "It raises the question of ..."
- "It makes me wonder ..."
- "The idea that X seems Y, but I think Z ..." (state a claim only to immediately soften it)
- "This really highlights ..."
Also banned: summarizing the video back at its own creator ("Evans's argument about names...",
"Rudolf Steiner's notion of archetypes..."). The audience already watched the video. Restating
its thesis in tidier language is not a comment, it's a recap, and it reads as a bot that
skimmed a transcript.

WORKED EXAMPLES:

GOOD — "Bertrand Russell walks into a bar and orders a drink. The bartender asks, 'What will
you have?' Russell replies, 'That depends on what you mean by "have"!' Guess he was just
trying to avoid definite descriptions!"
Why it works: specific to the actual philosopher and the actual concept the video covers, it
is a real joke with a punchline, and it sounds like someone who knows the material, not
someone reviewing it.

BAD — "Evans's argument about names lacking intrinsic meaning really challenges traditional
views. It raises the question of how we even attach significance to names..."
Why it fails: hedged-reviewer tells ("really challenges traditional views", "It raises the
question of") and it summarizes the video's thesis back at the viewer instead of reacting to
it. There's no person in it, so nobody clicks the name.

BAD — "Rudolf Steiner's notion of archetypes as the foundation of reality really challenges our
conventional understanding. How often do we actually consider..."
Why it fails: same tell ("really challenges our conventional understanding"), same recap
structure, and it ends by gesturing at a question instead of committing to one — it could be
pasted under any video that mentions archetypes.

COMMIT TO ONE THING. State a single point of view and stop. No "but on the other hand," no
both-sides hedge, no softening the claim right after making it. A comment that couldn't offend
or surprise anyone has already failed — if every viewer would nod along, rewrite it. This does
not mean being cruel; it means having a stance.

VOICE. Write like one opinionated person typing fast on their phone because the video just made
them react, not like someone drafting a review. Contractions are normal. A sentence fragment is
fine. It should read like a reaction, not a synopsis.

SPECIFICITY. Every variant must anchor to at least one actual particular from this video — a
name, a number, a specific claim, a specific moment — used in passing, not as a topic summary.
Generic-but-on-topic (a line that would work equally well on any video about this subject) is a
failure exactly like off-topic is.

A comment does NOT have to be a question. Treat a question as one option among several, not the
default reflex — a flat declarative claim, a short anecdote, or a plain observation are just as
valid, and a batch that leans on questions for most of its variants has failed this brief.

Write {n} DIFFERENT comments that differ in FORM, not just topic: vary sentence shape (statement,
anecdote, aside, question — pick freely, don't default to question), vary length (some
one-clause, some two sentences), and vary register (deadpan, wry, matter-of-fact, mildly
argumentative). No two variants should scan the same way out loud even before you read the words.

Each variant gets a different style_tag from:
- provocative_question: a question the video's own argument leaves genuinely open (use
  sparingly — this is one register among four, not the house style), not a softball a
  reasonable viewer already knows the answer to
- joke: actually funny and specific to the subject, not a pun on the title
- contrarian_take: a real disagreement with the video's premise, not a mild qualification of it
- insight: a fact or connection the video did not say, that adds something new

STYLE-TAG HONESTY. The tag must match the text, not just the topic. If you write "joke" the
text must contain an actual joke, not a wry observation. If you write "contrarian_take" the
text must actually disagree with something the video claims, not add nuance to it. If you write
"insight" it must say something the video itself did not say. If you write "provocative_question"
the question must be one the video leaves genuinely unresolved, not one it already answered. If
a variant you've drafted does not honestly earn its tag, throw it out and write a different
variant instead of mislabeling it.

Output ONLY valid JSON:
{{"variants": [{{"text": "...", "style_tag": "..."}}]}}"""

USER_TMPL = """Video title: {title}

What the video is about: {summary}"""

# Appended to SYSTEM (after `{n}` is filled in) when a grounded `Moment` is supplied. Kept
# separate from SYSTEM itself so SYSTEM.format(n=...) — used directly by
# test_system_format_example_block_is_valid_json — is unaffected.
MOMENT_ADDENDUM = """

REACT TO ONE REAL MOMENT. Below is a specific moment from THIS video: a verbatim quote, when it
happens, and why it stands out. React to THAT moment — disagree with it, extend it, push back on
it, or joke about it. Do not summarize the video's overall thesis; respond the way a real viewer
reacts to one thing that just happened on screen, not the way a reviewer describes a video.

{cite_instruction}"""

CITE_ON = ("CITE THE TIMESTAMP. This moment is self-contained enough that a stranger scrolling "
           "comments would get it without watching. Reference the timestamp naturally in your "
           "reaction (for example: \"at 12:33 when he says...\"), so it reads as a pointer to a "
           "specific spot, not a citation.")
CITE_OFF = ("DO NOT CITE THE TIMESTAMP. Do not mention the time or say anything like \"at "
            "12:33\" anywhere in any variant. React to what the moment says, not when it "
            "happens.")

USER_MOMENT_TMPL = """Video title: {title}

What the video is about: {summary}

The moment to react to, at {stamp}:
"{quote}"

Why it stands out: {why}"""


class Variant(BaseModel):
    text: str
    style_tag: str


def _strip_fence(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return m.group(1).strip() if m else raw.strip()


def variants(title: str, topic_summary: str, provider: str = "", n: int = 3,
             complete=None, moment: Moment | None = None, cite: bool = False) -> list[Variant]:
    """Generate up to `n` candidate comments. Any failure yields [] — never raises.

    With `moment=None` (the default) this is title-and-summary only, unchanged from before.
    When `moment` is given, the prompt shows its verbatim quote, stamped timestamp, and `why`,
    and instructs the model to react to that specific moment rather than summarize the video.
    `cite` controls whether the reaction is allowed to name the timestamp — callers should pass
    `highlight.should_cite(moment)`."""
    try:
        if complete is None:
            from studio.providers import llm
            complete = llm.complete
        provider = provider or default_provider("script")

        system = SYSTEM.format(n=n)
        if moment is not None:
            cite_instruction = CITE_ON if cite else CITE_OFF
            system += MOMENT_ADDENDUM.format(cite_instruction=cite_instruction)
            user = USER_MOMENT_TMPL.format(title=title, summary=topic_summary,
                                            stamp=tr.stamp(moment.timestamp),
                                            quote=moment.quote, why=moment.why)
        else:
            user = USER_TMPL.format(title=title, summary=topic_summary)

        raw = complete(provider, system, user)
        data = json.loads(_strip_fence(raw))

        out: list[Variant] = []
        for item in data.get("variants", []):
            text = (item.get("text") or "").strip()
            if not text or len(text) > MAX_LEN:
                continue
            tag = item.get("style_tag", "")
            out.append(Variant(text=text, style_tag=tag if tag in STYLE_TAGS else "insight"))
        return out
    except Exception:
        return []
