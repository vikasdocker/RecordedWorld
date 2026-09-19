"""Tests for Phase 28: Observability — tracing, error tracking, metrics."""

import pytest
import time
from app.services.observability_service import (
    Tracer, ErrorTracker, Span, TraceStatus,
    tracer, error_tracker,
)


class TestTracer:
    def test_start_span(self):
        """Can start a span."""
        t = Tracer()
        span = t.start_span("test_operation")
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.operation == "test_operation"

    def test_finish_span(self):
        """Can finish a span."""
        t = Tracer()
        span = t.start_span("test_op")
        t.finish_span(span)
        assert span.end_time is not None
        assert span.duration_ms >= 0

    def test_trace_id(self):
        """Spans share trace_id."""
        t = Tracer()
        span1 = t.start_span("op1", trace_id="abc123")
        span2 = t.start_span("op2", trace_id="abc123")
        assert span1.trace_id == span2.trace_id == "abc123"

    def test_parent_span(self):
        """Child spans have parent."""
        t = Tracer()
        parent = t.start_span("parent")
        child = t.start_span("child", parent_span_id=parent.span_id)
        assert child.parent_span_id == parent.span_id

    def test_get_trace(self):
        """Can get trace by ID."""
        t = Tracer()
        s1 = t.start_span("op1", trace_id="trace1")
        t.finish_span(s1)
        s2 = t.start_span("op2", trace_id="trace1")
        t.finish_span(s2)
        trace = t.get_trace("trace1")
        assert len(trace) == 2

    def test_get_slow_queries(self):
        """Can get slow spans."""
        t = Tracer()
        span = t.start_span("slow_op")
        span.finish()
        # Force long duration
        span.start_time -= 0.2
        t.finish_span(span)
        slow = t.get_slow_queries(threshold_ms=100)
        assert len(slow) >= 1

    def test_get_error_spans(self):
        """Can get error spans."""
        t = Tracer()
        span = t.start_span("error_op")
        t.finish_span(span)
        span.status = TraceStatus.ERROR  # Set after finish_span for test
        errors = t.get_error_spans()
        assert len(errors) >= 1

    def test_span_events(self):
        """Can add events to span."""
        span = Span(
            trace_id="t1", span_id="s1", parent_span_id=None,
            operation="test", service="backend", start_time=time.time(),
        )
        span.add_event("event1", {"key": "value"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "event1"

    def test_get_stats(self):
        """Can get stats."""
        t = Tracer()
        span = t.start_span("test")
        t.finish_span(span)
        stats = t.get_stats()
        assert stats["total_spans"] >= 1

    def test_global_tracer(self):
        """Global tracer exists."""
        assert tracer is not None


class TestErrorTracker:
    def test_capture_exception(self):
        """Can capture exception."""
        et = ErrorTracker()
        try:
            raise ValueError("test error")
        except ValueError as e:
            error_id = et.capture_exception(e, context={"key": "value"})
        assert error_id is not None

    def test_capture_message(self):
        """Can capture message."""
        et = ErrorTracker()
        error_id = et.capture_message("Something went wrong", level="warning")
        assert error_id is not None

    def test_get_errors(self):
        """Can get errors."""
        et = ErrorTracker()
        et.capture_message("error 1")
        et.capture_message("error 2")
        errors = et.get_errors()
        assert len(errors) == 2

    def test_get_error_count(self):
        """Can get error count."""
        et = ErrorTracker()
        et.capture_message("error 1")
        assert et.get_error_count() == 1

    def test_get_stats(self):
        """Can get stats."""
        et = ErrorTracker()
        try:
            raise TypeError("type error")
        except TypeError as e:
            et.capture_exception(e)
        et.capture_message("msg")
        stats = et.get_stats()
        assert stats["total_errors"] == 2
        assert "TypeError" in stats["by_type"]

    def test_global_tracker(self):
        """Global error tracker exists."""
        assert error_tracker is not None
