"""The four subjects and the channel matrix (plan B1, B2)."""
import pytest

from app.subjects import (NO_SELF_PROMOTION, Channel, Reach, SUBJECTS,
                          channels_for, get_subject, self_promotion_allowed)
from app.subjects.definitions import matrix


class TestCompleteness:
    def test_four_subjects_exactly(self):
        assert set(SUBJECTS) == {"pet_health", "vet_news", "ai_health", "regenerative"}

    def test_every_subject_assigns_every_channel(self):
        """A channel missing from a map defaults to SKIP, which is a silent
        decision. Requiring every channel to be named makes it a stated one."""
        for sid, subject in SUBJECTS.items():
            missing = [c.value for c in Channel if c not in subject.channels]
            assert not missing, f"{sid} does not say what to do with {missing}"

    def test_every_subject_publishes_somewhere(self):
        for sid, subject in SUBJECTS.items():
            assert subject.publishes_to, f"{sid} has no channel to publish to"

    def test_every_subject_has_audience_register_and_level(self):
        for sid, subject in SUBJECTS.items():
            assert subject.audience and subject.register and subject.reading_level, sid

    def test_every_subject_explains_its_channel_mix(self):
        for sid, subject in SUBJECTS.items():
            assert len(subject.rationale) > 30, f"{sid} has no stated rationale"

    def test_participating_subjects_name_their_subreddits(self):
        """"Participate on Reddit" is useless without knowing where."""
        for sid, subject in SUBJECTS.items():
            if Channel.REDDIT in subject.channels_with(Reach.PARTICIPATE, Reach.PRIMARY):
                assert subject.subreddits, f"{sid} uses Reddit but names no subreddits"


class TestConfirmedDecisions:
    def test_linkedin_on_vet_news_and_ai_health_only(self):
        """Decision 0.8, as confirmed."""
        on = {sid for sid, s in SUBJECTS.items()
              if s.reach(Channel.LINKEDIN) is not Reach.SKIP}
        assert on == {"vet_news", "ai_health"}

    def test_website_reaches_every_subject(self):
        """Decision 0.7: one article per subject per month means all four need
        the website as a destination."""
        for sid, subject in SUBJECTS.items():
            assert subject.reach(Channel.WEBSITE) in (Reach.PRIMARY, Reach.SECONDARY), sid

    def test_peer_subjects_skip_the_short_form_channels(self):
        for sid in ("vet_news", "ai_health"):
            subject = SUBJECTS[sid]
            assert subject.reach(Channel.INSTAGRAM) is Reach.SKIP
            assert subject.reach(Channel.TIKTOK) is Reach.SKIP


class TestBannedFramings:
    def test_every_subject_bans_something(self):
        for sid, subject in SUBJECTS.items():
            assert subject.banned_framings, f"{sid} bans no framings"

    def test_owner_facing_health_bans_diagnosis_and_prescribing(self):
        """The two that put a licence at risk."""
        banned = " ".join(SUBJECTS["pet_health"].banned_framings).lower()
        assert "diagnos" in banned and "prescrib" in banned

    def test_longevity_bans_the_claim_it_is_surrounded_by(self):
        banned = " ".join(SUBJECTS["regenerative"].banned_framings).lower()
        assert "reverses ageing" in banned or "reverses aging" in banned
        assert "mouse" in banned

    def test_colleague_subject_bans_identifiable_case_detail(self):
        banned = " ".join(SUBJECTS["vet_news"].banned_framings).lower()
        assert "identifiable" in banned


class TestSelfPromotionRule:
    def test_reddit_disallows_self_promotion(self):
        assert not self_promotion_allowed(Channel.REDDIT)

    def test_every_other_channel_allows_it(self):
        for channel in Channel:
            if channel is not Channel.REDDIT:
                assert self_promotion_allowed(channel), channel

    def test_the_rule_holds_even_where_reddit_is_primary(self):
        """ai_health posts to Reddit as PRIMARY. The rule is a property of the
        channel, not of the reach, which is exactly the confusion it prevents."""
        assert SUBJECTS["ai_health"].reach(Channel.REDDIT) is Reach.PRIMARY
        assert Channel.REDDIT in NO_SELF_PROMOTION


class TestLookups:
    def test_unknown_subject_names_the_known_ones(self):
        with pytest.raises(ValueError, match="pet_health"):
            get_subject("cardiology")

    def test_channels_for_defaults_to_publishable(self):
        assert channels_for("vet_news") == SUBJECTS["vet_news"].publishes_to

    def test_channel_order_is_stable(self):
        """Declaration order, not dict-insertion order, so output does not
        shuffle between runs."""
        assert channels_for("vet_news") == channels_for("vet_news")
        assert SUBJECTS["ai_health"].channels_with(Reach.PRIMARY) == [
            Channel.LINKEDIN, Channel.YOUTUBE, Channel.REDDIT]

    def test_matrix_covers_every_subject(self):
        rows = matrix()
        assert len(rows) == len(SUBJECTS)
        assert all(r["rationale"] for r in rows)
