"""Tests for core/activity_log.py — the in-memory command history."""

from __future__ import annotations

from pbnightingale.core import activity_log


def test_starts_empty():
    assert activity_log.entries() == []


def test_record_appends_an_entry():
    activity_log.record("gpg --list-keys")

    entries = activity_log.entries()
    assert len(entries) == 1
    assert entries[0].command == "gpg --list-keys"


def test_entries_are_returned_oldest_first():
    activity_log.record("first")
    activity_log.record("second")

    assert [e.command for e in activity_log.entries()] == ["first", "second"]


def test_configure_caps_the_ring_buffer_size():
    activity_log.configure(2)
    activity_log.record("first")
    activity_log.record("second")
    activity_log.record("third")

    assert [e.command for e in activity_log.entries()] == ["second", "third"]


def test_configure_keeps_the_most_recent_entries_when_shrinking():
    activity_log.record("first")
    activity_log.record("second")
    activity_log.record("third")

    activity_log.configure(2)

    assert [e.command for e in activity_log.entries()] == ["second", "third"]


def test_configure_clamps_below_one_to_one():
    activity_log.configure(0)
    activity_log.record("first")
    activity_log.record("second")

    assert [e.command for e in activity_log.entries()] == ["second"]


def test_seq_starts_at_one_and_increments():
    activity_log.record("first")
    activity_log.record("second")
    activity_log.record("third")

    assert [e.seq for e in activity_log.entries()] == [1, 2, 3]


def test_seq_is_not_reset_by_clear():
    activity_log.record("first")
    activity_log.record("second")

    activity_log.clear()
    activity_log.record("third")

    assert [e.seq for e in activity_log.entries()] == [3]


def test_seq_is_not_reset_when_the_ring_buffer_evicts_old_entries():
    activity_log.configure(2)
    activity_log.record("first")
    activity_log.record("second")
    activity_log.record("third")

    assert [e.seq for e in activity_log.entries()] == [2, 3]


def test_seq_is_reset_by_reset():
    activity_log.record("first")

    activity_log.reset()
    activity_log.record("second")

    assert [e.seq for e in activity_log.entries()] == [1]


def test_record_returns_the_entry():
    entry = activity_log.record("gpg --list-keys")

    assert entry.seq == 1
    assert entry.command == "gpg --list-keys"


def test_record_detail_shares_the_given_seq():
    command_entry = activity_log.record("gpg --attribute-file /tmp/x --list-keys")

    activity_log.record_detail(command_entry.seq, "attribute content")

    entries = activity_log.entries()
    assert [e.seq for e in entries] == [command_entry.seq, command_entry.seq]
    assert entries[1].command == "attribute content"


def test_record_detail_does_not_consume_a_new_seq():
    command_entry = activity_log.record("gpg --attribute-file /tmp/x --list-keys")
    activity_log.record_detail(command_entry.seq, "attribute content")

    next_entry = activity_log.record("gpg --list-keys")

    assert next_entry.seq == command_entry.seq + 1


def test_record_detail_notifies_subscribers():
    received = []
    activity_log.subscribe(received.append)
    command_entry = activity_log.record("gpg --attribute-file /tmp/x --list-keys")

    activity_log.record_detail(command_entry.seq, "attribute content")

    assert [e.command for e in received] == [
        "gpg --attribute-file /tmp/x --list-keys",
        "attribute content",
    ]


def test_clear_discards_entries():
    activity_log.record("first")
    activity_log.record("second")

    activity_log.clear()

    assert activity_log.entries() == []


def test_clear_keeps_subscribers_registered():
    received = []
    activity_log.subscribe(received.append)
    activity_log.record("first")

    activity_log.clear()
    activity_log.record("second")

    assert [e.command for e in received] == ["first", "second"]


def test_clear_keeps_the_configured_capacity():
    activity_log.configure(2)

    activity_log.clear()
    activity_log.record("first")
    activity_log.record("second")
    activity_log.record("third")

    assert [e.command for e in activity_log.entries()] == ["second", "third"]


def test_subscribe_is_called_with_each_new_entry():
    received = []
    activity_log.subscribe(received.append)

    activity_log.record("gpg --list-keys")

    assert len(received) == 1
    assert received[0].command == "gpg --list-keys"


def test_unsubscribe_stops_further_calls():
    received = []
    unsubscribe = activity_log.subscribe(received.append)
    unsubscribe()

    activity_log.record("gpg --list-keys")

    assert received == []


def test_unsubscribe_is_safe_to_call_twice():
    unsubscribe = activity_log.subscribe(lambda _entry: None)

    unsubscribe()
    unsubscribe()


def test_reset_clears_entries_and_subscribers():
    received = []
    activity_log.subscribe(received.append)
    activity_log.record("gpg --list-keys")

    activity_log.reset()

    assert activity_log.entries() == []

    activity_log.record("gpg --export")

    # The pre-reset subscriber is gone — it only ever saw the pre-reset
    # entry, never the one recorded afterward.
    assert [e.command for e in received] == ["gpg --list-keys"]
    assert [e.command for e in activity_log.entries()] == ["gpg --export"]
