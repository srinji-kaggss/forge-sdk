"""AUDIT-MATRIX-001 F6 — proves count-based Knowledge.id collides under a
realistic race (two evolution steps observing the same stale count).
Run: python3 specs/_audit_repros/repro_b_knowledge_id_collision.py
Expected: collision (duplicate id present): True (this is the BUG being demonstrated)."""
import tempfile, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from forge_sdk.harness.profiles import AgentProfile
from forge_sdk.harness.learning import LearningStore, Knowledge

with tempfile.TemporaryDirectory() as d:
    store = LearningStore(d)
    profile = AgentProfile(name="coder", domain="python")

    stale_count = 0  # both engines observed this count before either committed
    k1 = Knowledge(id=f"know-{stale_count}", rule="rule A", confidence=0.5,
                   domain="python", source_episodes=["ep-1"])
    k2 = Knowledge(id=f"know-{stale_count}", rule="rule B (different!)", confidence=0.5,
                   domain="python", source_episodes=["ep-3"])
    store.add_knowledge(k1)
    store.add_knowledge(k2)
    all_k = store.get_knowledge()
    ids = [k.id for k in all_k]
    print("knowledge count:", len(all_k))
    print("ids:", ids)
    print("collision (duplicate id present):", len(ids) != len(set(ids)))
