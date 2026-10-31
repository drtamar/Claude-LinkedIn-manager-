"""The four subjects, as data (plan B1).

A *subject* is an editorial beat: who a piece is for and how technical it may
be. It is not the author's voice — that lives on `UserProfile`
(`brand_voice_notes`, `content_tone`, `target_audience`) and applies to all
four. The writer in Stage E gets both: voice from the profile, register and
audience from here.

Deliberately not database rows. These are settings that change when the
editorial plan changes, not per-user data, so they belong in version control
where a change is reviewable. Adding a fifth subject is one entry below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Channel(str, Enum):
    WEBSITE = "website"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    TIKTOK = "tiktok"


class Reach(str, Enum):
    """How hard a subject pushes on a channel (plan B2).

    PARTICIPATE is not a weaker PRIMARY — it is a different activity. On those
    channels the system drafts answers to other people's questions and never
    posts promotional material. The critic enforces it.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    PARTICIPATE = "participate"
    SKIP = "skip"


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    audience: str
    register: str
    # Target reading level, used by the translator in Stage E1.
    reading_level: str
    # Channel -> how we use it. Channels absent from the map are SKIP.
    channels: dict[Channel, Reach]
    # Framings the critic rejects for this subject. These are the failure
    # modes specific to the beat, not general style preferences.
    banned_framings: tuple[str, ...] = ()
    # Subreddits for PARTICIPATE/PRIMARY Reddit use, and seed sources for
    # Stage C's harvester.
    subreddits: tuple[str, ...] = ()
    example_sources: tuple[str, ...] = ()
    # Shown in the UI so the reason for the channel mix is visible where the
    # decision gets questioned.
    rationale: str = ""

    def reach(self, channel: Channel) -> Reach:
        return self.channels.get(channel, Reach.SKIP)

    def channels_with(self, *reaches: Reach) -> list[Channel]:
        """Channels at any of the given reaches, in Channel declaration order
        so output is stable rather than dict-insertion dependent."""
        wanted = set(reaches)
        return [c for c in Channel if self.channels.get(c) in wanted]

    @property
    def publishes_to(self) -> list[Channel]:
        """Channels this subject actually posts original content to."""
        return self.channels_with(Reach.PRIMARY, Reach.SECONDARY)

    @property
    def participates_in(self) -> list[Channel]:
        return self.channels_with(Reach.PARTICIPATE)


PET_HEALTH = Subject(
    id="pet_health",
    name="Pet health",
    audience="Pet owners",
    register="Warm, practical, reassuring. Plain words for clinical ideas.",
    reading_level="grade_8",
    channels={
        Channel.INSTAGRAM: Reach.PRIMARY,
        Channel.WEBSITE: Reach.PRIMARY,
        Channel.TIKTOK: Reach.SECONDARY,
        Channel.YOUTUBE: Reach.SECONDARY,
        Channel.REDDIT: Reach.PARTICIPATE,
        Channel.LINKEDIN: Reach.SKIP,
    },
    banned_framings=(
        "diagnosing a specific animal the reader describes",
        "prescribing a dose, drug or treatment plan",
        "telling an owner not to see a vet",
        "scare framing that drives a clinic visit",
    ),
    subreddits=("AskVet", "dogs", "cats", "Pets"),
    example_sources=("JAVMA", "Veterinary Practice News", "dvm360"),
    rationale=(
        "Owners search symptoms, so the website earns search traffic that "
        "outlives a post. Instagram is where the same people already are."
    ),
)

VET_NEWS = Subject(
    id="vet_news",
    name="Veterinary news",
    audience="Veterinary colleagues",
    register="Peer-to-peer and technical. Assumes clinical training.",
    reading_level="professional",
    channels={
        Channel.WEBSITE: Reach.PRIMARY,
        Channel.LINKEDIN: Reach.PRIMARY,
        Channel.YOUTUBE: Reach.SECONDARY,
        Channel.REDDIT: Reach.PARTICIPATE,
        Channel.INSTAGRAM: Reach.SKIP,
        Channel.TIKTOK: Reach.SKIP,
    },
    banned_framings=(
        "explaining basic clinical concepts to qualified vets",
        "identifiable case detail — breed plus location plus timing",
        "presenting a single study as settled practice",
    ),
    subreddits=("veterinary",),
    example_sources=(
        "JAVMA", "Veterinary Record", "VIN News Service (public feed)",
        "PubMed", "ClinicalTrials.gov",
    ),
    rationale=(
        "LinkedIn is where vets are professionally. Instagram and TikTok are "
        "skipped on purpose: a colleague seeing clinical content as a Reel "
        "reads it as marketing."
    ),
)

AI_HEALTH = Subject(
    id="ai_health",
    name="AI, technology and health",
    audience="Technically literate and curious readers",
    register="Analytical and sceptical. Names what the evidence does not show.",
    reading_level="technical_curious",
    channels={
        Channel.REDDIT: Reach.PRIMARY,
        Channel.LINKEDIN: Reach.PRIMARY,
        Channel.YOUTUBE: Reach.PRIMARY,
        Channel.WEBSITE: Reach.SECONDARY,
        Channel.INSTAGRAM: Reach.SKIP,
        Channel.TIKTOK: Reach.SKIP,
    },
    banned_framings=(
        "AI will replace clinicians",
        "benchmark results described as clinical validation",
        "vendor claims repeated without an independent source",
    ),
    subreddits=("artificial", "medicine", "MachineLearning"),
    example_sources=("PubMed", "Europe PMC", "arXiv", "medRxiv"),
    rationale=(
        "These subreddits reward substance and punish promotion, so the "
        "sceptical register is the one that travels. A clinician who can read "
        "the papers is rare in this conversation."
    ),
)

REGENERATIVE = Subject(
    id="regenerative",
    name="Regenerative medicine and ageing",
    audience="Everyone — general but motivated readers",
    register="Credible and myth-correcting. Separates the finding from the hype.",
    reading_level="grade_10",
    channels={
        Channel.YOUTUBE: Reach.PRIMARY,
        Channel.INSTAGRAM: Reach.SECONDARY,
        Channel.TIKTOK: Reach.SECONDARY,
        Channel.WEBSITE: Reach.SECONDARY,
        Channel.REDDIT: Reach.PARTICIPATE,
        Channel.LINKEDIN: Reach.SKIP,
    },
    banned_framings=(
        "reverses ageing",
        "a mouse result described as a human result",
        "recommending a supplement, protocol or clinic",
        "implying a treatment is available when it is in trials",
    ),
    subreddits=("longevity", "Biohackers", "AgingBiology"),
    example_sources=(
        "PubMed", "bioRxiv", "ClinicalTrials.gov", "Retraction Watch",
    ),
    rationale=(
        "Longevity is a large YouTube category and saturated with "
        "overclaiming, which is exactly what makes a credentialed clinician "
        "grading the evidence worth following. Stage D does the grading."
    ),
)

SUBJECTS: dict[str, Subject] = {
    s.id: s for s in (PET_HEALTH, VET_NEWS, AI_HEALTH, REGENERATIVE)
}


def subject_ids() -> list[str]:
    return list(SUBJECTS)


def get_subject(subject_id: str) -> Subject:
    try:
        return SUBJECTS[subject_id]
    except KeyError:
        raise ValueError(
            f"Unknown subject {subject_id!r}. Known subjects: "
            f"{', '.join(SUBJECTS)}."
        ) from None


def channels_for(subject_id: str, *reaches: Reach) -> list[Channel]:
    """Channels for a subject at the given reaches (default: ones we post to)."""
    subject = get_subject(subject_id)
    if not reaches:
        return subject.publishes_to
    return subject.channels_with(*reaches)


# Channels where promoting your own work is against the culture or the rules,
# whatever reach a subject assigns them. AI-health posts to Reddit as PRIMARY
# because a well-argued read of a paper is welcome there — but "look at my
# article" is not, and the two are easy to confuse when drafting. The critic
# (E4.4) reads this rather than inferring the rule from Reach.
NO_SELF_PROMOTION: frozenset[Channel] = frozenset({Channel.REDDIT})


def self_promotion_allowed(channel: Channel) -> bool:
    return channel not in NO_SELF_PROMOTION


def matrix() -> list[dict]:
    """The channel matrix, shaped for the CLI and the UI."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "audience": s.audience,
            "reading_level": s.reading_level,
            "primary": [c.value for c in s.channels_with(Reach.PRIMARY)],
            "secondary": [c.value for c in s.channels_with(Reach.SECONDARY)],
            "participate": [c.value for c in s.participates_in],
            "skip": [c.value for c in s.channels_with(Reach.SKIP)],
            "subreddits": list(s.subreddits),
            "rationale": s.rationale,
        }
        for s in SUBJECTS.values()
    ]
