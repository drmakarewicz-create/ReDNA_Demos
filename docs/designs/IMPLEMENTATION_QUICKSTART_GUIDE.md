# Evergreen Implementation Quick-Start Guide

**For:** Codex (Implementation Agent)
**Date:** 2025-10-12
**Status:** Ready for Phase 1 Execution

---

## 🚀 Getting Started

This guide provides a step-by-step path to implement all Evergreen designs. Follow this sequence to ensure smooth, dependency-aware implementation.

---

## 📋 Pre-Implementation Checklist

Before writing any code:

- [ ] Read all design documents in `docs/designs/`
- [ ] Review the [README.md](README.md) for navigation
- [ ] Understand the [Session Summary](EVERGREEN_SESSION_SUMMARY_2025_10_12.md)
- [ ] Verify Python environment (Python 3.9+)
- [ ] Ensure access to OpenAI API or LLM service
- [ ] Check database/storage setup
- [ ] Review existing codebase structure

---

## 🗂️ Implementation Order (Dependency-Aware)

### Week 1-2: Phase 1 - Foundation

#### Day 1-2: Setup & Data Ingestion Core

**Priority 1: Create Directory Structure**

```bash
# Create ingestion module
mkdir -p ReDNACoreDemo/core/ingestion
touch ReDNACoreDemo/core/ingestion/__init__.py

# Create curiosity module
mkdir -p ReDNACoreDemo/core/curiosity
touch ReDNACoreDemo/core/curiosity/__init__.py

# Create tools module
mkdir -p ReDNACoreDemo/tools
touch ReDNACoreDemo/tools/__init__.py

# Create test directories
mkdir -p ReDNACoreDemo/tests/ingestion
mkdir -p ReDNACoreDemo/tests/curiosity
mkdir -p ReDNACoreDemo/tests/empathy
mkdir -p ReDNACoreDemo/tests/tools
```

**Priority 2: Implement PreProcessor**

Reference: [EVERGREEN_9_DATA_INGESTION_ARCHITECTURE.md](EVERGREEN_9_DATA_INGESTION_ARCHITECTURE.md) Section 3.2.1

```python
# File: ReDNACoreDemo/core/ingestion/preprocessor.py

from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class NormalizedData:
    """Normalized data format for ingestion pipeline."""
    source_type: str  # CHAT, FILE, THIRD_PARTY, BEHAVIOR
    timestamp: str  # ISO 8601
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    sensitivity_hint: int  # 1-10

class DataPreprocessor:
    """Normalize and prepare data for ingestion."""

    def __init__(self):
        self.format_handlers = {
            'text/plain': self._handle_text,
            'application/json': self._handle_json,
            'text/markdown': self._handle_markdown,
        }

    def process(self, raw_data: Dict[str, Any]) -> NormalizedData:
        """Main processing entry point."""
        # Detect format
        format_type = self._detect_format(raw_data)

        # Handle format-specific processing
        handler = self.format_handlers.get(format_type, self._handle_generic)
        processed = handler(raw_data)

        # Extract metadata
        metadata = self._extract_metadata(raw_data, format_type)

        # Calculate sensitivity hint
        sensitivity = self._calculate_sensitivity_hint(processed)

        return NormalizedData(
            source_type=raw_data.get('source_type', 'CHAT'),
            timestamp=datetime.now().isoformat(),
            content=processed,
            metadata=metadata,
            sensitivity_hint=sensitivity
        )

    def _detect_format(self, data: Dict[str, Any]) -> str:
        """Detect data format."""
        # Implementation here
        pass

    # Add other methods...

# Unit test example
def test_preprocessor():
    preprocessor = DataPreprocessor()
    raw = {
        'source_type': 'CHAT',
        'data': 'Hello world',
        'user_id': 'TEST_USER'
    }
    result = preprocessor.process(raw)
    assert result.source_type == 'CHAT'
    assert result.content is not None
```

**Test Command:**
```bash
cd ReDNACoreDemo
python -m pytest tests/ingestion/test_preprocessor.py -v
```

#### Day 3-4: Comfort Index Filter

**Priority 3: Implement ComfortIndexFilter**

Reference: [EVERGREEN_9_COMFORT_INDEX_SPEC.md](EVERGREEN_9_COMFORT_INDEX_SPEC.md) Section 4.1

```python
# File: ReDNACoreDemo/core/ingestion/comfort_filter.py

from enum import Enum
from typing import Optional
import json
import re

class FilterAction(Enum):
    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"
    ANONYMIZE = "anonymize"

class ComfortIndexFilter:
    """User safety gate for data ingestion."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.config = self._load_config(user_id)

    def apply_filter(self, data: NormalizedData) -> FilterResult:
        """Apply comfort filter."""
        # Check sensitivity threshold
        if data.sensitivity_hint > self.config['max_sensitivity_level']:
            return FilterResult(
                action=FilterAction.BLOCK,
                reason=f"Sensitivity {data.sensitivity_hint} exceeds max"
            )

        # Check data type permissions
        if not self._is_type_allowed(data.source_type):
            return FilterResult(
                action=FilterAction.REVIEW,
                reason=f"Type {data.source_type} requires review"
            )

        # Apply content filters
        content_result = self._check_content_filters(data.content)
        if content_result.action != FilterAction.PASS:
            return content_result

        return FilterResult(
            action=FilterAction.PASS,
            reason="All checks passed"
        )

    def _load_config(self, user_id: str) -> Dict:
        """Load user's comfort configuration."""
        config_path = f"data/users/{user_id}/comfort_index.json"
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Conservative default comfort settings."""
        return {
            "max_sensitivity_level": 5,
            "allowed_types": ["CHAT"],
            "pii_detection_enabled": True,
            # ... rest of defaults
        }

    # Add PII detection methods...
```

**Test Command:**
```bash
python -m pytest tests/ingestion/test_comfort_filter.py -v
```

#### Day 5-7: Storage & Provenance

**Priority 4: Core Storage Layer**

```python
# File: ReDNACoreDemo/core/ingestion/storage.py

import os
import json
from datetime import datetime
from pathlib import Path

class CoreStorage:
    """Persistent storage layer for ingested data."""

    def __init__(self, base_path: str = "data/users"):
        self.base_path = base_path

    def store(self, user_id: str, data: NormalizedData, provenance: Dict) -> str:
        """Store data with provenance."""
        # Create user directory structure
        user_dir = Path(self.base_path) / user_id / "ingested"
        user_dir.mkdir(parents=True, exist_ok=True)

        # Generate data ID
        data_id = self._generate_data_id()

        # Store data
        data_path = user_dir / f"{data_id}.json"
        with open(data_path, 'w') as f:
            json.dump({
                'data_id': data_id,
                'data': data.__dict__,
                'provenance': provenance,
                'stored_at': datetime.now().isoformat()
            }, f, indent=2)

        # Index for fast retrieval
        self._update_index(user_id, data_id, data)

        return data_id

    def retrieve(self, user_id: str, data_id: str) -> Optional[Dict]:
        """Retrieve data by ID."""
        data_path = Path(self.base_path) / user_id / "ingested" / f"{data_id}.json"
        if data_path.exists():
            with open(data_path, 'r') as f:
                return json.load(f)
        return None

    # Add indexing, query methods...
```

**Priority 5: Provenance Tagging**

```python
# File: ReDNACoreDemo/core/ingestion/provenance.py

from datetime import datetime
from typing import List, Dict
import uuid

class ProvenanceTagger:
    """Create audit trail for all data."""

    def create_provenance(self,
                         data_id: str,
                         source: Dict,
                         chain: List[Dict]) -> Dict:
        """Generate complete provenance record."""
        return {
            "provenance_id": f"prov_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "data_id": data_id,
            "source": source,
            "chain_of_custody": chain,
            "created_at": datetime.now().isoformat()
        }

    def add_chain_event(self,
                       stage: str,
                       processor_version: str,
                       result: str) -> Dict:
        """Add event to chain of custody."""
        return {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "processor": processor_version,
            "result": result
        }
```

#### Day 8-10: Curiosity Foundation

**Priority 6: Core Analyzer**

Reference: [EVERGREEN_6_CURIOSITY_ENGINE_V3.md](EVERGREEN_6_CURIOSITY_ENGINE_V3.md) Section 3.1

```python
# File: ReDNACoreDemo/core/curiosity/core_analyzer.py

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ContainerAnalysis:
    container_id: str
    namespace: str
    fullness: float  # 0.0-1.0
    confidence: float
    importance: float
    last_explored: Optional[datetime]
    related_containers: List[str]

class CoreAnalyzer:
    """Analyze user ontology for gaps."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def analyze_user_ontology(self) -> List[ContainerAnalysis]:
        """Scan for unexplored containers."""
        # Load user's ontology
        ontology = self._load_user_ontology()

        # Load container patterns
        patterns = self._load_container_patterns()

        analyses = []
        for container in patterns:
            analysis = self._analyze_container(container, ontology)
            analyses.append(analysis)

        return analyses

    def _analyze_container(self, container: Dict, ontology: Dict) -> ContainerAnalysis:
        """Analyze single container."""
        user_data = ontology.get(container['id'], {})

        return ContainerAnalysis(
            container_id=container['id'],
            namespace=container['namespace'],
            fullness=self._calculate_fullness(user_data, container),
            confidence=self._calculate_confidence(user_data),
            importance=container.get('importance', 0.5),
            last_explored=self._find_last_exploration(container['id']),
            related_containers=container.get('related', [])
        )

    def _calculate_fullness(self, user_data: Dict, container: Dict) -> float:
        """Calculate how full container is with user data."""
        if not container.get('expected_traits'):
            return 0.0

        expected_count = len(container['expected_traits'])
        present_count = len(user_data.get('traits', []))

        return min(present_count / expected_count, 1.0)

    # Add other calculation methods...
```

**Test Command:**
```bash
python -m pytest tests/curiosity/test_core_analyzer.py -v
```

#### Day 11-14: Empathy Foundation

**Priority 7: Empathy Engine**

Reference: [EVERGREEN_2_HC_EMPATHY_BONDING_SPEC.md](EVERGREEN_2_HC_EMPATHY_BONDING_SPEC.md) Section 2.2

```python
# File: ReDNACoreDemo/core/hc_empathy.py

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional

class EmotionalState(Enum):
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    NEUTRAL = "neutral"

@dataclass
class EmpathyModel:
    emotional_state: EmotionalState
    intensity: float
    cognitive_understanding: Dict
    needs_assessment: List[str]
    appropriate_responses: List[str]
    confidence: float

class EmpathyEngine:
    """Advanced empathy modeling."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history = self._load_emotional_history()

    async def analyze_user_state(self, context: Dict) -> EmpathyModel:
        """Analyze current emotional/cognitive state."""
        # Collect signals
        signals = await self._collect_signals(context)

        # Detect emotion
        emotion = self._detect_emotion(signals)

        # Build understanding
        cognitive = self._build_cognitive_understanding(context, emotion)

        # Assess needs
        needs = self._assess_needs(emotion, cognitive, context)

        # Generate responses
        responses = self._generate_responses(emotion, needs, context)

        return EmpathyModel(
            emotional_state=emotion,
            intensity=self._calculate_intensity(signals),
            cognitive_understanding=cognitive,
            needs_assessment=needs,
            appropriate_responses=responses,
            confidence=self._calculate_confidence(signals)
        )

    async def _collect_signals(self, context: Dict) -> List:
        """Collect empathy signals from context."""
        signals = []

        # Linguistic signals
        if 'message' in context:
            signals.extend(self._analyze_linguistic(context['message']))

        # Temporal signals
        signals.extend(self._analyze_temporal(context))

        # Behavioral signals
        signals.extend(self._analyze_behavioral(context))

        return signals

    # Add signal analysis methods...
```

---

### Week 3-4: Phase 2 - Intelligence

#### Week 3: Enrichment & Distribution

**Priority 8: Enrichment Engine**

```python
# File: ReDNACoreDemo/core/ingestion/enrichment.py

class EnrichmentEngine:
    """Map data to ontology and extract relationships."""

    async def enrich(self, data: NormalizedData, user_id: str) -> Dict:
        """Enrich data with ontology mapping."""
        # Map to containers
        containers = await self._map_containers(data)

        # Extract traits
        traits = await self._extract_traits(data, containers)

        # Discover relationships
        relationships = await self._discover_relationships(data, user_id)

        return {
            'mapped_containers': containers,
            'extracted_traits': traits,
            'relationships': relationships,
            'enrichment_timestamp': datetime.now().isoformat()
        }

    # Implementation methods...
```

**Priority 9: Distribution Layer**

```python
# File: ReDNACoreDemo/core/ingestion/distribution.py

class DistributionLayer:
    """Make data available across system."""

    def __init__(self):
        self.event_bus = EventBus()
        self.cache = SharedCache()

    async def distribute(self, data_id: str, enriched_data: Dict):
        """Distribute enriched data."""
        # Publish to event bus
        await self.event_bus.publish('data_ingested', {
            'data_id': data_id,
            'enriched': enriched_data
        })

        # Update cache
        self.cache.set(data_id, enriched_data)

        # Notify subscribers
        await self._notify_subscribers(data_id, enriched_data)
```

#### Week 4: Dynamic Systems

**Priority 10: Dynamic Reprioritizer**

**Priority 11: Question Generator**

**Priority 12: Bonding Monitor**

---

### Week 5-6: Phase 3 - Tools & Integration

#### Week 5: Tool Modules

**Priority 13: Financial Planner**
**Priority 14: Mood Tracker**
**Priority 15: Goal Engine**
**Priority 16: Habit Designer**

#### Week 6: Integration

**Priority 17: HC Orchestrator Integration**
**Priority 18: API Endpoints**
**Priority 19: Tool Manager**

---

### Week 7-8: Phase 4 - Testing & Polish

**Priority 20: Integration Tests**
**Priority 21: Performance Optimization**
**Priority 22: Documentation**

---

## 🧪 Testing Strategy

### Unit Tests (As You Go)

For each module, create corresponding test file:

```python
# Example: tests/ingestion/test_preprocessor.py

import pytest
from ReDNACoreDemo.core.ingestion.preprocessor import DataPreprocessor

def test_text_processing():
    preprocessor = DataPreprocessor()
    result = preprocessor.process({
        'source_type': 'CHAT',
        'data': 'Test message',
        'user_id': 'TEST'
    })
    assert result.source_type == 'CHAT'
    assert result.content is not None

def test_sensitivity_calculation():
    # Test sensitivity hint calculation
    pass

# Run: pytest tests/ingestion/test_preprocessor.py -v
```

### Integration Tests (Week 7)

```python
# tests/integration/test_ingestion_pipeline.py

async def test_end_to_end_ingestion():
    """Test complete pipeline flow."""
    # Create test data
    raw_data = create_test_data()

    # Run through pipeline
    result = await run_ingestion_pipeline(raw_data, "TEST_USER")

    # Verify each stage
    assert result['preprocessed'] is not None
    assert result['comfort_filtered'] is not None
    assert result['stored'] is True
    assert result['enriched'] is not None
    assert result['distributed'] is True
```

---

## 📝 Code Quality Standards

### Style Guide
- Follow PEP 8
- Use type hints
- Document all public methods
- Keep functions under 50 lines

### Example Format

```python
def calculate_metric(data: List[Dict], threshold: float = 0.5) -> float:
    """
    Calculate metric from data.

    Args:
        data: List of data dictionaries
        threshold: Minimum threshold (default 0.5)

    Returns:
        Calculated metric value

    Raises:
        ValueError: If data is empty
    """
    if not data:
        raise ValueError("Data cannot be empty")

    # Implementation
    result = sum(d['value'] for d in data) / len(data)
    return max(result, threshold)
```

---

## 🔍 Debugging Tips

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.debug("Processing data: %s", data)
```

### Use Breakpoints

```python
import pdb

def problematic_function(data):
    # Set breakpoint
    pdb.set_trace()
    # Debug from here
    result = process(data)
    return result
```

---

## ✅ Daily Checklist

At end of each day:

- [ ] All new code has unit tests
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] Git commit with clear message
- [ ] Update progress log in EVERGREEN_SPRINT_PROMPTS.md

---

## 🆘 Getting Help

### Design Questions
- Reference specific section in design docs
- Check flowcharts in EVERGREEN_9_INGESTION_FLOWCHART.md
- Review code examples in specs

### Implementation Issues
- Check existing codebase for patterns
- Review similar components
- Consult integration test examples

---

## 🎯 Success Criteria

### By End of Phase 1
- [ ] All core modules created and tested
- [ ] Basic pipeline working end-to-end
- [ ] Unit test coverage > 80%

### By End of Phase 2
- [ ] Enrichment and distribution functional
- [ ] Dynamic systems operational
- [ ] Integration tests passing

### By End of Phase 3
- [ ] All tools implemented
- [ ] HC orchestrator integrated
- [ ] API endpoints live

### By End of Phase 4
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Ready for production

---

**Status:** Ready to begin implementation
**Next Step:** Day 1 - Setup & PreProcessor
**Estimated Completion:** 8 weeks from start
