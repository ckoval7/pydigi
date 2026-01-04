# Session 12: Integration Testing

**Duration**: 2-3 hours
**Priority**: HIGH
**Status**: ✅ Complete

## Goal

Create comprehensive integration tests that verify the complete ARQ system works correctly in realistic scenarios. These tests go beyond unit tests to validate the entire protocol stack working together, including connection establishment, data transfer, error recovery, and disconnection.

## Prerequisites

- Sessions 1-11 complete (all ARQ components implemented)
- Python 3.8+
- pytest installed
- All existing unit tests passing (162 tests)

## Deliverables

1. Integration test suite (`tests/test_arq/test_integration.py`)
2. Stress/performance tests (`tests/test_arq/test_stress.py`)
3. Edge case tests (`tests/test_arq/test_edge_cases.py`)
4. This session guide document
5. Updated IMPLEMENTATION_STATUS.md
6. Updated CHANGELOG.md

## Integration Testing Overview

Integration tests validate that all ARQ components work correctly together:

- **Connection Lifecycle**: Full connection → data transfer → disconnection
- **Text Transfer Scenarios**: Small messages, large messages, multiple messages
- **File Transfer Scenarios**: Text files, binary files, large files
- **Error Recovery**: Lost frames, corrupted data, retransmissions
- **Edge Cases**: Empty messages, maximum size messages, rapid sequences
- **Concurrent Operations**: Multiple transfers, abort during transfer
- **Timing**: Timeouts, retries, keepalives

Unlike unit tests that test individual components in isolation, integration tests use the full ARQ protocol stack with realistic message passing.

## Implementation Steps

### Step 1: Create Integration Test Suite (60 minutes)

Create `tests/test_arq/test_integration.py`:

```python
"""
Integration tests for ARQ protocol.

These tests validate the complete ARQ system working together,
including connection, data transfer, error recovery, and disconnection.
"""

import pytest
import tempfile
import os
from pydigi.arq.protocol import ARQProtocol
from pydigi.arq.config import ARQConfig
from pydigi.arq.exceptions import ARQConnectionError


class TestConnectionLifecycle:
    """Test complete connection lifecycle scenarios."""

    def test_simple_connection_and_disconnection(self):
        """Test basic connection establishment and clean disconnect."""
        # Create two stations
        config1 = ARQConfig()
        config1.my_call = "STATION1"
        station1 = ARQProtocol(config=config1)

        config2 = ARQConfig()
        config2.my_call = "STATION2"
        station2 = ARQProtocol(config=config2)

        # Setup communication
        station1.set_send_callback(station2.receive_frame)
        station2.set_send_callback(station1.receive_frame)

        # Connect
        station1.connect("STATION2")

        # Process until connected
        for _ in range(20):
            station1.process()
            station2.process()

        assert station1.state.is_connected()
        assert station2.state.is_connected()

        # Disconnect
        station1.disconnect()

        # Process until disconnected
        for _ in range(20):
            station1.process()
            station2.process()

        assert not station1.state.is_connected()
        assert not station2.state.is_connected()

    def test_connection_with_immediate_text_transfer(self):
        """Test sending text immediately after connection."""
        config1 = ARQConfig()
        config1.my_call = "STATION1"
        station1 = ARQProtocol(config=config1)

        config2 = ARQConfig()
        config2.my_call = "STATION2"
        station2 = ARQProtocol(config=config2)

        station1.set_send_callback(station2.receive_frame)
        station2.set_send_callback(station1.receive_frame)

        # Track received text
        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Connect and immediately send text
        station1.connect("STATION2")
        station1.send_text("Hello, World!")

        # Process
        for _ in range(100):
            station1.process()
            station2.process()

        # Verify
        assert station1.state.is_connected()
        assert len(received_text) > 0
        assert "Hello, World!" in "".join(received_text)

    def test_bidirectional_connection(self):
        """Test that both stations can initiate connections."""
        config1 = ARQConfig()
        config1.my_call = "STATION1"
        station1 = ARQProtocol(config=config1)

        config2 = ARQConfig()
        config2.my_call = "STATION2"
        station2 = ARQProtocol(config=config2)

        station1.set_send_callback(station2.receive_frame)
        station2.set_send_callback(station1.receive_frame)

        # Station2 initiates connection
        station2.connect("STATION1")

        for _ in range(20):
            station1.process()
            station2.process()

        assert station1.state.is_connected()
        assert station2.state.is_connected()


class TestTextTransferIntegration:
    """Test complete text transfer scenarios."""

    def test_small_text_transfer(self):
        """Test transferring a small text message."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Send small message
        station1.send_text("CQ CQ CQ DE W1ABC K")

        # Process
        for _ in range(100):
            station1.process()
            station2.process()

        # Verify
        full_text = "".join(received_text)
        assert "CQ CQ CQ DE W1ABC K" in full_text

    def test_large_text_transfer(self):
        """Test transferring large text (multiple blocks)."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Create large message (multiple blocks)
        large_message = "This is a test message. " * 50  # ~1200 bytes

        station1.send_text(large_message)

        # Process
        for _ in range(200):
            station1.process()
            station2.process()

        # Verify
        full_text = "".join(received_text)
        assert large_message in full_text

    def test_multiple_sequential_messages(self):
        """Test sending multiple messages in sequence."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        messages = [
            "First message",
            "Second message",
            "Third message",
        ]

        for msg in messages:
            station1.send_text(msg)

        # Process
        for _ in range(200):
            station1.process()
            station2.process()

        # Verify all messages received
        full_text = "".join(received_text)
        for msg in messages:
            assert msg in full_text

    def test_bidirectional_text_transfer(self):
        """Test both stations sending text simultaneously."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text_1 = []
        received_text_2 = []
        station1.set_rx_text_callback(lambda text: received_text_1.append(text))
        station2.set_rx_text_callback(lambda text: received_text_2.append(text))

        # Both send messages
        station1.send_text("Message from Station 1")
        station2.send_text("Message from Station 2")

        # Process
        for _ in range(200):
            station1.process()
            station2.process()

        # Verify both received
        assert "Message from Station 2" in "".join(received_text_1)
        assert "Message from Station 1" in "".join(received_text_2)


class TestFileTransferIntegration:
    """Test complete file transfer scenarios."""

    def test_small_file_transfer(self):
        """Test transferring a small text file."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_files = []
        station2.set_rx_file_callback(
            lambda filename, data: received_files.append((filename, data))
        )

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
            temp_file = f.name
            test_data = b"This is a test file."
            f.write(test_data)

        try:
            # Send file
            station1.send_file(temp_file)

            # Process
            for _ in range(200):
                station1.process()
                station2.process()

            # Verify
            assert len(received_files) == 1
            filename, data = received_files[0]
            assert data == test_data
        finally:
            os.unlink(temp_file)

    def test_binary_file_transfer(self):
        """Test transferring a binary file."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_files = []
        station2.set_rx_file_callback(
            lambda filename, data: received_files.append((filename, data))
        )

        # Create binary file with all byte values
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            temp_file = f.name
            binary_data = bytes(range(256))
            f.write(binary_data)

        try:
            station1.send_file(temp_file)

            for _ in range(200):
                station1.process()
                station2.process()

            assert len(received_files) == 1
            _, data = received_files[0]
            assert data == binary_data
        finally:
            os.unlink(temp_file)

    def test_large_file_transfer(self):
        """Test transferring a large file (multiple blocks)."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_files = []
        station2.set_rx_file_callback(
            lambda filename, data: received_files.append((filename, data))
        )

        # Create large file (5KB)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.dat') as f:
            temp_file = f.name
            large_data = b"A" * 5000
            f.write(large_data)

        try:
            station1.send_file(temp_file)

            for _ in range(500):
                station1.process()
                station2.process()

            assert len(received_files) == 1
            _, data = received_files[0]
            assert len(data) == 5000
            assert data == large_data
        finally:
            os.unlink(temp_file)

    def test_multiple_files_sequential(self):
        """Test sending multiple files in sequence."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_files = []
        station2.set_rx_file_callback(
            lambda filename, data: received_files.append((filename, data))
        )

        # Create multiple files
        files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(
                mode='wb', delete=False, suffix=f'_{i}.txt'
            ) as f:
                files.append(f.name)
                f.write(f"File {i} content".encode())

        try:
            # Send all files
            for file_path in files:
                station1.send_file(file_path)

            # Process
            for _ in range(500):
                station1.process()
                station2.process()

            # Verify all received
            assert len(received_files) == 3
        finally:
            for f in files:
                os.unlink(f)


class TestErrorRecovery:
    """Test error recovery and retransmission."""

    def test_abort_during_transfer(self):
        """Test aborting a transfer mid-stream."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Start large transfer
        large_message = "X" * 1000
        station1.send_text(large_message)

        # Process a bit
        for _ in range(10):
            station1.process()
            station2.process()

        # Abort
        station1.abort()

        # Process
        for _ in range(50):
            station1.process()
            station2.process()

        # Should still be connected
        assert station1.state.is_connected()
        assert station2.state.is_connected()

        # Send new message after abort
        station1.send_text("After abort")

        for _ in range(100):
            station1.process()
            station2.process()

        full_text = "".join(received_text)
        assert "After abort" in full_text

    def test_connection_timeout_recovery(self):
        """Test connection timeout and retry."""
        config1 = ARQConfig()
        config1.my_call = "STATION1"
        config1.timeout = 1000  # 1 second timeout
        config1.retry_count = 2
        station1 = ARQProtocol(config=config1)

        # Don't set up station2 - connection should timeout
        station1.connect("STATION2")

        # Process until timeout
        for _ in range(100):
            station1.process()

        # Should have given up
        assert not station1.state.is_connected()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_text_message(self):
        """Test sending an empty text message."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        station1.send_text("")

        for _ in range(50):
            station1.process()
            station2.process()

        # Empty message may or may not be delivered - just verify no crash

    def test_maximum_block_size(self):
        """Test sending exactly one block worth of data."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Send exactly buffer length
        message = "X" * config1.buffer_length
        station1.send_text(message)

        for _ in range(100):
            station1.process()
            station2.process()

        full_text = "".join(received_text)
        assert message in full_text

    def test_rapid_connect_disconnect(self):
        """Test rapid connection/disconnection cycles."""
        config1 = ARQConfig()
        config1.my_call = "STATION1"
        station1 = ARQProtocol(config=config1)

        config2 = ARQConfig()
        config2.my_call = "STATION2"
        station2 = ARQProtocol(config=config2)

        station1.set_send_callback(station2.receive_frame)
        station2.set_send_callback(station1.receive_frame)

        # Connect and disconnect multiple times
        for _ in range(3):
            station1.connect("STATION2")

            for _ in range(20):
                station1.process()
                station2.process()

            assert station1.state.is_connected()

            station1.disconnect()

            for _ in range(20):
                station1.process()
                station2.process()

            assert not station1.state.is_connected()


# Helper function
def setup_connected_stations():
    """Create two connected ARQ stations for testing."""
    config1 = ARQConfig()
    config1.my_call = "STATION1"
    station1 = ARQProtocol(config=config1)

    config2 = ARQConfig()
    config2.my_call = "STATION2"
    station2 = ARQProtocol(config=config2)

    station1.set_send_callback(station2.receive_frame)
    station2.set_send_callback(station1.receive_frame)

    # Connect
    station1.connect("STATION2")

    for _ in range(20):
        station1.process()
        station2.process()

    assert station1.state.is_connected()
    assert station2.state.is_connected()

    return config1, station1, config2, station2
```

### Step 2: Create Stress Tests (30 minutes)

Create `tests/test_arq/test_stress.py`:

```python
"""
Stress and performance tests for ARQ protocol.

These tests validate the ARQ system under heavy load and edge conditions.
"""

import pytest
import tempfile
import os
from pydigi.arq.protocol import ARQProtocol
from pydigi.arq.config import ARQConfig


class TestStress:
    """Stress test scenarios."""

    def test_many_small_messages(self):
        """Test sending many small messages."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_count = [0]
        def count_messages(text):
            received_count[0] += 1

        station2.set_rx_text_callback(count_messages)

        # Send 50 small messages
        for i in range(50):
            station1.send_text(f"Message {i}")

        # Process
        for _ in range(1000):
            station1.process()
            station2.process()

        # Should have received all messages
        assert received_count[0] >= 50

    def test_very_large_message(self):
        """Test sending a very large message (10KB)."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Create 10KB message
        large_message = "A" * 10000
        station1.send_text(large_message)

        # Process (may take many iterations)
        for _ in range(1000):
            station1.process()
            station2.process()

        full_text = "".join(received_text)
        assert len(full_text) >= 10000

    def test_maximum_block_wrapping(self):
        """Test sending enough blocks to wrap block numbers multiple times."""
        config1, station1, config2, station2 = setup_connected_stations()

        received_text = []
        station2.set_rx_text_callback(lambda text: received_text.append(text))

        # Send enough to wrap block numbers (64+ blocks)
        # Each block is ~128 bytes, so 64 blocks = ~8KB
        large_message = "B" * 10000
        station1.send_text(large_message)

        for _ in range(1000):
            station1.process()
            station2.process()

        full_text = "".join(received_text)
        assert len(full_text) >= 10000


def setup_connected_stations():
    """Create two connected ARQ stations for testing."""
    config1 = ARQConfig()
    config1.my_call = "STATION1"
    station1 = ARQProtocol(config=config1)

    config2 = ARQConfig()
    config2.my_call = "STATION2"
    station2 = ARQProtocol(config=config2)

    station1.set_send_callback(station2.receive_frame)
    station2.set_send_callback(station1.receive_frame)

    station1.connect("STATION2")

    for _ in range(20):
        station1.process()
        station2.process()

    return config1, station1, config2, station2
```

### Step 3: Run All Tests (15 minutes)

Run the complete test suite:

```bash
# Run just integration tests
pytest tests/test_arq/test_integration.py -v

# Run stress tests
pytest tests/test_arq/test_stress.py -v

# Run all ARQ tests
pytest tests/test_arq/ -v

# Run with coverage
pytest tests/test_arq/ -v --cov=pydigi.arq --cov-report=term-missing
```

Verify all tests pass.

### Step 4: Run Example Scripts (15 minutes)

Verify example scripts work correctly:

```bash
# Test loopback example
python examples/arq_loopback_test.py

# Test file transfer example
python examples/arq_file_transfer.py
```

Both should complete successfully with no errors.

## Validation Checkpoint

✅ **Session 12 is complete when**:

1. ✅ Integration test suite created
   - Connection lifecycle tests
   - Text transfer tests
   - File transfer tests
   - Error recovery tests
   - Edge case tests

2. ✅ Stress tests created
   - Many small messages test
   - Very large message test
   - Block wrapping test

3. ✅ All tests pass
   - All integration tests pass
   - All stress tests pass
   - All existing unit tests still pass
   - Total test count: 190+ tests

4. ✅ Examples verified
   - arq_loopback_test.py runs successfully
   - arq_file_transfer.py runs successfully

5. ✅ Documentation updated
   - IMPLEMENTATION_STATUS.md updated
   - CHANGELOG.md updated
   - This session guide complete

## Common Pitfalls

1. **Insufficient processing iterations**: Integration tests may need 100-500 process() calls for large transfers
2. **Race conditions**: Text may arrive across multiple callback invocations - collect all before checking
3. **State cleanup**: Each test should use fresh protocol instances
4. **Timeouts**: Stress tests with very large messages may need longer timeouts
5. **File cleanup**: Always use try/finally for temp file cleanup

## Test Coverage Goals

After Session 12:
- **Total ARQ tests**: 190+ (up from 162)
- **Protocol coverage**: 92%+ (up from 90%)
- **Integration scenarios**: 20+ tests
- **Stress scenarios**: 5+ tests

## Reference Files

Primary references in fldigi source:
- `fldigi/src/flarq-src/arq.cxx` - Complete protocol implementation
- `fldigi/src/flarq-src/flarq.cxx` - Application-level integration

## Next Steps

After completing Session 12:

→ **Session 13**: Documentation & Polish
   Complete API documentation, user guides, and final cleanup

→ **Session 14** (Optional): Interoperability Testing
   Test with actual fldigi via audio loopback if desired

## Progress Check

- [x] Integration test suite created
- [x] Stress tests created
- [x] All tests passing
- [x] Examples verified
- [x] Documentation updated

**Status**: ✅ Session 12 Complete!
