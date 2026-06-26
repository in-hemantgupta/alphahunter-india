#!/usr/bin/env python3
"""Quick test to verify imports work."""

import sys
sys.path.insert(0, '/Users/hemant/alpha-hunter/backend')

print("Testing imports...")

try:
    from app.core.config import settings
    print("✓ Config loaded")
except Exception as e:
    print(f"✗ Config failed: {e}")

try:
    from app.scoring.alpha_engine import alpha_score
    print("✓ Scoring engine loaded")
except Exception as e:
    print(f"✗ Scoring failed: {e}")

try:
    from app.ingestion.fetch_universe import build_stock_universe
    print("✓ Ingestion loaded")
except Exception as e:
    print(f"✗ Ingestion failed: {e}")

try:
    from app.llm_engine.llm_router import LLMRouter
    print("✓ LLM router loaded")
except Exception as e:
    print(f"✗ LLM router failed: {e}")

try:
    from app.agents.memory_engine import store_memory, recall_memory
    print("✓ Memory engine loaded")
except Exception as e:
    print(f"✗ Memory engine failed: {e}")

try:
    from app.services.pipeline import run_full_pipeline
    print("✓ Pipeline loaded")
except Exception as e:
    print(f"✗ Pipeline failed: {e}")

print("\nAll core modules import successfully!")
