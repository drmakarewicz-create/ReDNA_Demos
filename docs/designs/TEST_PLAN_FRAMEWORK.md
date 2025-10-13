# Evergreen Test Plan Framework

**Version:** 1.0
**Date:** 2025-10-12
**Purpose:** Comprehensive testing strategy for all Evergreen implementations

---

## Overview

This document provides a complete testing framework covering unit tests, integration tests, performance tests, and user acceptance criteria for all Evergreen components.

---

## 1. Testing Philosophy

### Testing Principles

1. **Test Early, Test Often** - Write tests alongside code
2. **Test Pyramid** - Many unit tests, fewer integration tests, minimal E2E
3. **Behavior-Driven** - Test what the system should do, not how
4. **Realistic Data** - Use production-like test data
5. **Isolated Tests** - Each test should be independent
6. **Fast Feedback** - Unit tests run in milliseconds

### Coverage Goals

- **Unit Test Coverage:** ≥80%
- **Integration Test Coverage:** Critical paths 100%
- **Performance Tests:** All major operations
- **Security Tests:** All user-facing endpoints

---

## 2. Unit Testing

### 2.1 Evergreen 9: Data Ingestion

#### PreProcessor Tests

```python
# tests/ingestion/test_preprocessor.py

import pytest
from ReDNACoreDemo.core.ingestion.preprocessor import DataPreprocessor, NormalizedData

class TestDataPreprocessor:
    """Unit tests for DataPreprocessor."""

    @pytest.fixture
    def preprocessor(self):
        return DataPreprocessor()

    def test_text_processing(self, preprocessor):
        """Test basic text processing."""
        raw = {
            'source_type': 'CHAT',
            'data': 'Hello world',
            'user_id': 'TEST_USER',
            'metadata': {}
        }
        result = preprocessor.process(raw)

        assert isinstance(result, NormalizedData)
        assert result.source_type == 'CHAT'
        assert result.content is not None
        assert 'Hello world' in str(result.content)

    def test_json_processing(self, preprocessor):
        """Test JSON data processing."""
        raw = {
            'source_type': 'FILE',
            'data': '{"key": "value"}',
            'user_id': 'TEST_USER',
            'metadata': {'format': 'json'}
        }
        result = preprocessor.process(raw)

        assert result.source_type == 'FILE'
        assert result.content['structured'] == {'key': 'value'}

    def test_sensitivity_calculation(self, preprocessor):
        """Test sensitivity hint calculation."""
        # Low sensitivity
        raw_low = {
            'source_type': 'CHAT',
            'data': 'I like blue',
            'user_id': 'TEST_USER',
            'metadata': {}
        }
        result_low = preprocessor.process(raw_low)
        assert result_low.sensitivity_hint <= 3

        # High sensitivity
        raw_high = {
            'source_type': 'CHAT',
            'data': 'My SSN is 123-45-6789',
            'user_id': 'TEST_USER',
            'metadata': {}
        }
        result_high = preprocessor.process(raw_high)
        assert result_high.sensitivity_hint >= 8

    def test_metadata_extraction(self, preprocessor):
        """Test metadata extraction."""
        raw = {
            'source_type': 'FILE',
            'data': 'Test content',
            'user_id': 'TEST_USER',
            'metadata': {
                'filename': 'test.txt',
                'size': 12
            }
        }
        result = preprocessor.process(raw)

        assert 'filename' in result.metadata
        assert result.metadata['size_bytes'] == 12

    def test_invalid_input(self, preprocessor):
        """Test error handling for invalid input."""
        with pytest.raises(ValueError):
            preprocessor.process({'invalid': 'data'})

        with pytest.raises(TypeError):
            preprocessor.process(None)

# Run: pytest tests/ingestion/test_preprocessor.py -v
```

#### Comfort Filter Tests

```python
# tests/ingestion/test_comfort_filter.py

import pytest
from ReDNACoreDemo.core.ingestion.comfort_filter import ComfortIndexFilter, FilterAction

class TestComfortIndexFilter:
    """Unit tests for ComfortIndexFilter."""

    @pytest.fixture
    def filter_instance(self, tmp_path):
        """Create test filter with mock config."""
        # Create test user directory
        user_dir = tmp_path / "data" / "users" / "TEST_USER"
        user_dir.mkdir(parents=True)

        # Create test comfort config
        config_path = user_dir / "comfort_index.json"
        config_path.write_text('{"max_sensitivity_level": 5, "allowed_types": ["CHAT"]}')

        return ComfortIndexFilter("TEST_USER")

    def test_pass_low_sensitivity(self, filter_instance):
        """Test that low sensitivity data passes."""
        data = create_test_data(sensitivity=3, type='CHAT')
        result = filter_instance.apply_filter(data)

        assert result.action == FilterAction.PASS
        assert "passed" in result.reason.lower()

    def test_block_high_sensitivity(self, filter_instance):
        """Test that high sensitivity data is blocked."""
        data = create_test_data(sensitivity=9, type='CHAT')
        result = filter_instance.apply_filter(data)

        assert result.action == FilterAction.BLOCK
        assert result.requires_user_consent == True

    def test_review_disallowed_type(self, filter_instance):
        """Test that disallowed types require review."""
        data = create_test_data(sensitivity=3, type='FILE')
        result = filter_instance.apply_filter(data)

        assert result.action == FilterAction.REVIEW

    def test_pii_detection_email(self, filter_instance):
        """Test email PII detection."""
        data = create_test_data_with_content(
            'Contact me at john@example.com'
        )
        result = filter_instance.apply_filter(data)

        assert result.action in [FilterAction.ANONYMIZE, FilterAction.REVIEW]
        assert 'pii' in result.reason.lower() or 'email' in result.detected_issues

    def test_pii_detection_ssn(self, filter_instance):
        """Test SSN PII detection."""
        data = create_test_data_with_content('SSN: 123-45-6789')
        result = filter_instance.apply_filter(data)

        assert result.action == FilterAction.BLOCK
        assert 'ssn' in result.detected_issues

    def test_anonymization(self, filter_instance):
        """Test that anonymization modifies data."""
        data = create_test_data_with_content(
            'Email john@example.com and phone 555-1234'
        )
        result = filter_instance.apply_filter(data)

        if result.action == FilterAction.ANONYMIZE:
            assert result.modified_data is not None
            assert 'john@example.com' not in str(result.modified_data.content)

# Helper functions
def create_test_data(sensitivity, type):
    return NormalizedData(
        source_type=type,
        timestamp='2025-10-12T12:00:00Z',
        content={'text': 'test'},
        metadata={},
        sensitivity_hint=sensitivity
    )

def create_test_data_with_content(content):
    return NormalizedData(
        source_type='CHAT',
        timestamp='2025-10-12T12:00:00Z',
        content={'text': content},
        metadata={},
        sensitivity_hint=5
    )
```

#### Storage Tests

```python
# tests/ingestion/test_storage.py

import pytest
from pathlib import Path
from ReDNACoreDemo.core.ingestion.storage import CoreStorage

class TestCoreStorage:
    """Unit tests for CoreStorage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create storage with temp directory."""
        return CoreStorage(base_path=str(tmp_path))

    def test_store_and_retrieve(self, storage):
        """Test basic store and retrieve."""
        data = create_test_normalized_data()
        provenance = {'provenance_id': 'test_prov'}

        # Store
        data_id = storage.store('TEST_USER', data, provenance)
        assert data_id is not None

        # Retrieve
        retrieved = storage.retrieve('TEST_USER', data_id)
        assert retrieved is not None
        assert retrieved['data_id'] == data_id
        assert retrieved['provenance']['provenance_id'] == 'test_prov'

    def test_retrieve_nonexistent(self, storage):
        """Test retrieving non-existent data."""
        result = storage.retrieve('TEST_USER', 'nonexistent_id')
        assert result is None

    def test_query_by_source_type(self, storage):
        """Test querying by source type."""
        # Store multiple data points
        for i in range(5):
            data = create_test_normalized_data(source_type='CHAT')
            storage.store('TEST_USER', data, {})

        for i in range(3):
            data = create_test_normalized_data(source_type='FILE')
            storage.store('TEST_USER', data, {})

        # Query CHAT only
        results = storage.query('TEST_USER', {'source_type': 'CHAT'})
        assert len(results) == 5
        assert all(r['data']['source_type'] == 'CHAT' for r in results)

    def test_query_date_range(self, storage):
        """Test querying by date range."""
        # Store data with different timestamps
        # Implementation...
        pass

    def test_concurrent_writes(self, storage):
        """Test concurrent write safety."""
        # Use threading to test concurrent stores
        # Implementation...
        pass
```

---

### 2.2 Evergreen 6: Curiosity Engine

#### Core Analyzer Tests

```python
# tests/curiosity/test_core_analyzer.py

import pytest
from ReDNACoreDemo.core.curiosity.core_analyzer import CoreAnalyzer, ContainerAnalysis

class TestCoreAnalyzer:
    """Unit tests for CoreAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        return CoreAnalyzer('TEST_USER')

    def test_fullness_calculation_empty(self, analyzer):
        """Test fullness for empty container."""
        container = {
            'id': 'test.container',
            'expected_traits': ['trait1', 'trait2', 'trait3']
        }
        user_data = {}

        fullness = analyzer._calculate_fullness(user_data, container)
        assert fullness == 0.0

    def test_fullness_calculation_partial(self, analyzer):
        """Test fullness for partially filled container."""
        container = {
            'id': 'test.container',
            'expected_traits': ['trait1', 'trait2', 'trait3', 'trait4']
        }
        user_data = {
            'traits': {
                'trait1': {'value': 'x', 'confidence': 0.8},
                'trait2': {'value': 'y', 'confidence': 0.7}
            }
        }

        fullness = analyzer._calculate_fullness(user_data, container)
        assert 0.3 < fullness < 0.6  # 2/4 traits, adjusted for quality

    def test_fullness_calculation_full(self, analyzer):
        """Test fullness for fully filled container."""
        container = {
            'id': 'test.container',
            'expected_traits': ['trait1', 'trait2']
        }
        user_data = {
            'traits': {
                'trait1': {'value': 'x', 'confidence': 0.9},
                'trait2': {'value': 'y', 'confidence': 0.95}
            }
        }

        fullness = analyzer._calculate_fullness(user_data, container)
        assert fullness > 0.9

    def test_importance_calculation(self, analyzer):
        """Test importance calculation."""
        container = {
            'id': 'BeliefDNA.core_values.honesty',
            'metadata': {'importance': 0.9}
        }

        importance = analyzer.determine_importance(container, 'TEST_USER')
        assert importance > 0.8  # High base + context boost

    def test_analyze_user_ontology(self, analyzer):
        """Test full ontology analysis."""
        analyses = analyzer.analyze_user_ontology()

        assert isinstance(analyses, list)
        assert len(analyses) > 0
        assert all(isinstance(a, ContainerAnalysis) for a in analyses)
```

#### Curiosity Debt Tracker Tests

```python
# tests/curiosity/test_debt_tracker.py

import pytest
from datetime import datetime, timedelta
from ReDNACoreDemo.core.curiosity.debt_tracker import CuriosityDebtTracker

class TestCuriosityDebtTracker:
    """Unit tests for CuriosityDebtTracker."""

    @pytest.fixture
    def tracker(self):
        return CuriosityDebtTracker('TEST_USER')

    def test_age_debt_never_explored(self, tracker):
        """Test age debt for never-explored container."""
        age_debt = tracker.calculate_age_debt(None)
        assert age_debt == 0.8  # Max debt for never explored

    def test_age_debt_recent(self, tracker):
        """Test age debt for recently explored."""
        recent = datetime.now() - timedelta(days=3)
        age_debt = tracker.calculate_age_debt(recent)
        assert age_debt == 0.0  # No debt for recent

    def test_age_debt_old(self, tracker):
        """Test age debt for old exploration."""
        old = datetime.now() - timedelta(days=100)
        age_debt = tracker.calculate_age_debt(old)
        assert age_debt > 0.5  # High debt for old

    def test_debt_velocity_calculation(self, tracker):
        """Test debt velocity calculation."""
        # Set up history with increasing debt
        # Implementation...
        pass

    def test_high_debt_containers(self, tracker):
        """Test getting high-debt containers."""
        high_debt = tracker.get_high_debt_containers(threshold=0.6)

        assert isinstance(high_debt, list)
        assert all(d.debt_score >= 0.6 for d in high_debt)

    def test_debt_report_generation(self, tracker):
        """Test comprehensive debt report."""
        report = tracker.generate_debt_report()

        assert 'total_containers' in report
        assert 'high_debt_count' in report
        assert 'average_debt' in report
        assert 'highest_debt_containers' in report
```

---

### 2.3 Evergreen 2: Empathy & Bonding

#### Empathy Engine Tests

```python
# tests/empathy/test_empathy_engine.py

import pytest
from ReDNACoreDemo.core.hc_empathy import EmpathyEngine, EmotionalState

class TestEmpathyEngine:
    """Unit tests for EmpathyEngine."""

    @pytest.fixture
    def engine(self):
        return EmpathyEngine('TEST_USER')

    @pytest.mark.asyncio
    async def test_detect_joy(self, engine):
        """Test detection of joy."""
        context = {
            'current_message': 'I am so happy! This is amazing! 😊',
            'recent_messages': [],
            'session_metadata': {}
        }

        result = await engine.analyze_user_state(context)
        assert result.emotional_state == EmotionalState.JOY
        assert result.intensity > 0.6

    @pytest.mark.asyncio
    async def test_detect_sadness(self, engine):
        """Test detection of sadness."""
        context = {
            'current_message': 'I feel really down today. Nothing seems right.',
            'recent_messages': [],
            'session_metadata': {}
        }

        result = await engine.analyze_user_state(context)
        assert result.emotional_state == EmotionalState.SADNESS

    @pytest.mark.asyncio
    async def test_needs_assessment(self, engine):
        """Test needs assessment from emotional state."""
        context = {
            'current_message': 'I\'m anxious about this decision.',
            'recent_messages': [],
            'session_metadata': {}
        }

        result = await engine.analyze_user_state(context)
        assert 'reassurance' in result.needs_assessment or \
               'support' in result.needs_assessment

    def test_signal_collection(self, engine):
        """Test empathy signal collection."""
        context = {
            'current_message': 'Test message!',
            'recent_messages': ['previous message'],
            'session_metadata': {'session_length': 300}
        }

        signals = engine._collect_signals_sync(context)  # Sync version for testing
        assert len(signals) > 0
        assert any(s.signal_type == 'linguistic' for s in signals)
```

#### Bonding Monitor Tests

```python
# tests/empathy/test_bonding_monitor.py

import pytest
from ReDNACoreDemo.core.hc_empathy_monitor import BondingMonitor

class TestBondingMonitor:
    """Unit tests for BondingMonitor."""

    @pytest.fixture
    def monitor(self):
        return BondingMonitor()

    def test_calculate_trust_score(self, monitor):
        """Test trust score calculation."""
        history = create_test_interaction_history(
            vulnerability_count=10,
            recommendations_given=20,
            recommendations_followed=15
        )
        feedback = create_test_feedback(positive=18, negative=2)

        trust = monitor.calculate_trust_score(history, feedback)
        assert 0.6 < trust < 0.9  # High trust

    def test_calculate_trust_score_low(self, monitor):
        """Test low trust calculation."""
        history = create_test_interaction_history(
            vulnerability_count=1,
            recommendations_given=10,
            recommendations_followed=2
        )
        feedback = create_test_feedback(positive=3, negative=7)

        trust = monitor.calculate_trust_score(history, feedback)
        assert trust < 0.4  # Low trust

    def test_bonding_metrics_comprehensive(self, monitor):
        """Test comprehensive metrics calculation."""
        metrics = monitor.calculate_bonding_metrics('TEST_USER')

        assert 0 <= metrics.trust_score <= 1
        assert 0 <= metrics.positive_sentiment <= 1
        assert metrics.relationship_stage in ['early', 'developing', 'established', 'deep']

    def test_generate_recommendations(self, monitor):
        """Test recommendation generation."""
        metrics = create_test_metrics(
            trust_score=0.4,
            session_frequency=1.5,
            emotional_openness=0.3
        )

        recommendations = monitor.generate_recommendations(metrics)
        assert len(recommendations) > 0
        assert any('trust' in r.lower() for r in recommendations)
```

---

### 2.4 Evergreen 1: Tools

#### Financial Planner Tests

```python
# tests/tools/test_financial_planner.py

import pytest
from datetime import datetime
from ReDNACoreDemo.tools.financial_planner import FinancialPlanner

class TestFinancialPlanner:
    """Unit tests for FinancialPlanner."""

    @pytest.fixture
    def planner(self):
        return FinancialPlanner('TEST_USER')

    @pytest.mark.asyncio
    async def test_track_expense(self, planner):
        """Test expense tracking."""
        result = await planner.track_expense(
            amount=50.0,
            category='food',
            description='Groceries',
            date=datetime.now()
        )

        assert 'transaction' in result
        assert result['transaction']['amount'] == 50.0
        assert 'budget_status' in result

    @pytest.mark.asyncio
    async def test_set_financial_goal(self, planner):
        """Test goal setting."""
        result = await planner.set_financial_goal(
            name='Emergency Fund',
            target_amount=10000.0,
            target_date=datetime(2026, 1, 1),
            category='savings'
        )

        assert 'goal' in result
        assert result['goal'].target_amount == 10000.0
        assert 'savings_plan' in result
        assert 'feasibility_score' in result

    @pytest.mark.asyncio
    async def test_identify_savings_opportunities(self, planner):
        """Test savings opportunity detection."""
        # Set up test subscriptions
        # Implementation...
        pass

    def test_spending_pattern_analysis(self, planner):
        """Test spending pattern detection."""
        # Implementation...
        pass
```

---

## 3. Integration Testing

### 3.1 End-to-End Ingestion Pipeline

```python
# tests/integration/test_ingestion_pipeline.py

import pytest
from ReDNACoreDemo.core.ingestion.pipeline import IngestionPipeline

@pytest.mark.integration
class TestIngestionPipeline:
    """Integration tests for complete ingestion pipeline."""

    @pytest.fixture
    def pipeline(self):
        return IngestionPipeline()

    @pytest.mark.asyncio
    async def test_complete_flow_chat_data(self, pipeline):
        """Test complete pipeline with chat data."""
        raw_data = {
            'source_type': 'CHAT',
            'data': 'I love hiking in the mountains',
            'user_id': 'INTEGRATION_TEST_USER',
            'metadata': {}
        }

        result = await pipeline.ingest(raw_data)

        # Verify each stage
        assert result['preprocessed'] is not None
        assert result['comfort_result'].action == 'PASS'
        assert result['stored'] == True
        assert result['data_id'] is not None
        assert result['enriched'] is not None
        assert len(result['enriched']['mapped_containers']) > 0
        assert result['distributed'] == True

    @pytest.mark.asyncio
    async def test_complete_flow_with_pii(self, pipeline):
        """Test pipeline with PII content."""
        raw_data = {
            'source_type': 'CHAT',
            'data': 'Call me at 555-1234',
            'user_id': 'INTEGRATION_TEST_USER',
            'metadata': {}
        }

        result = await pipeline.ingest(raw_data)

        # Should be anonymized or require review
        assert result['comfort_result'].action in ['ANONYMIZE', 'REVIEW']

    @pytest.mark.asyncio
    async def test_complete_flow_high_sensitivity(self, pipeline):
        """Test pipeline with high sensitivity data."""
        raw_data = {
            'source_type': 'CHAT',
            'data': 'My password is secret123',
            'user_id': 'INTEGRATION_TEST_USER',
            'metadata': {}
        }

        result = await pipeline.ingest(raw_data)

        # Should be blocked
        assert result['comfort_result'].action == 'BLOCK'
        assert result['stored'] == False
```

### 3.2 Curiosity-Ingestion Integration

```python
# tests/integration/test_curiosity_ingestion.py

@pytest.mark.integration
class TestCuriosityIngestionIntegration:
    """Test curiosity and ingestion working together."""

    @pytest.mark.asyncio
    async def test_curiosity_reduces_debt_after_ingestion(self):
        """Test that answering curiosity questions reduces debt."""
        user_id = 'INTEGRATION_TEST_USER'

        # Get initial debt
        tracker = CuriosityDebtTracker(user_id)
        initial_debt = tracker.get_debt_for_container('test.container')

        # Ingest data that fills this container
        data = create_data_for_container('test.container')
        await ingest_data(data, user_id)

        # Check debt reduced
        final_debt = tracker.get_debt_for_container('test.container')
        assert final_debt.debt_score < initial_debt.debt_score
```

---

## 4. Performance Testing

### 4.1 Throughput Tests

```python
# tests/performance/test_ingestion_throughput.py

import pytest
import time

@pytest.mark.performance
class TestIngestionThroughput:
    """Performance tests for ingestion pipeline."""

    def test_single_item_latency(self, pipeline):
        """Test latency for single item."""
        start = time.time()

        data = create_test_data()
        pipeline.ingest_sync(data)

        latency = time.time() - start
        assert latency < 0.5  # Should complete in under 500ms

    def test_batch_throughput(self, pipeline):
        """Test throughput for batch ingestion."""
        batch_size = 100
        data_items = [create_test_data() for _ in range(batch_size)]

        start = time.time()
        for data in data_items:
            pipeline.ingest_sync(data)
        duration = time.time() - start

        throughput = batch_size / duration
        assert throughput > 10  # Should handle 10+ items/sec
```

### 4.2 Memory Tests

```python
# tests/performance/test_memory_usage.py

import pytest
import psutil
import os

@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage of components."""

    def test_storage_memory_leak(self, storage):
        """Test for memory leaks in storage."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Store 1000 items
        for i in range(1000):
            data = create_test_data()
            storage.store('TEST_USER', data, {})

        final_memory = process.memory_info().rss
        memory_increase_mb = (final_memory - initial_memory) / 1024 / 1024

        assert memory_increase_mb < 100  # Should not increase more than 100MB
```

---

## 5. Test Execution

### Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/ -v -m "not integration and not performance"

# Integration tests
pytest tests/ -v -m integration

# Performance tests
pytest tests/ -v -m performance

# Specific module
pytest tests/ingestion/ -v

# With coverage
pytest tests/ --cov=ReDNACoreDemo --cov-report=html

# Parallel execution
pytest tests/ -v -n auto
```

### Continuous Integration

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run unit tests
      run: pytest tests/ -v -m "not integration" --cov

    - name: Run integration tests
      run: pytest tests/ -v -m integration

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## 6. Test Data Management

### Test Fixtures

```python
# tests/conftest.py

import pytest
import tempfile
import shutil

@pytest.fixture(scope='session')
def test_data_dir():
    """Create temporary test data directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_user_id():
    """Standard test user ID."""
    return 'TEST_USER_' + str(uuid.uuid4())[:8]

@pytest.fixture
def sample_ontology():
    """Sample ontology for testing."""
    return {
        'containers': {
            'test.container': {
                'traits': {},
                'confidence': 0.5
            }
        }
    }
```

---

## Summary

This test framework ensures:
- **Comprehensive Coverage**: Unit, integration, performance, security
- **Quality Assurance**: 80%+ code coverage
- **Automated Testing**: CI/CD integration
- **Performance Validation**: Throughput and latency benchmarks
- **Maintainability**: Clear test structure and fixtures

**Status:** Complete test framework ready for implementation
**Coverage Goal:** 80%+ for all modules
**Test Types:** Unit, Integration, Performance, Security
