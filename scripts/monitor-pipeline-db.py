#!/usr/bin/env python3
"""Monitor seed script pipeline and database reasoning performance."""

import asyncio
import os
import psutil
import re
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
# Try to find project root from current working directory or script location
if Path.cwd().name == "nemotron-v3-home-security-intelligence":
    project_root = Path.cwd()
else:
    # Try relative to script location
    script_dir = Path(__file__).parent
    # Look for project root (contains backend/ directory)
    project_root = script_dir
    while project_root != project_root.parent:
        if (project_root / "backend").exists():
            break
        project_root = project_root.parent
    else:
        # Fallback: assume script is in /tmp, project is in home
        project_root = Path.home() / "github" / "nemotron-v3-home-security-intelligence"

sys.path.insert(0, str(project_root))
os.chdir(project_root)

# Load .env and fix DATABASE_URL for local execution (same as seed-events.py)
def fix_database_url():
    """Load .env file and fix DATABASE_URL for local execution."""
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    # Check for explicit external DATABASE_URL first
    external_url = os.environ.get("DATABASE_URL_EXTERNAL")
    if external_url:
        os.environ["DATABASE_URL"] = external_url
        return
    
    # Check if DATABASE_URL needs transformation for local execution
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return
    
    # Extract hostname and port from DATABASE_URL
    match = re.search(r"@([^:/@]+):(\d+)/", database_url)
    if not match:
        return
    
    hostname, port = match.groups()
    
    # Check if hostname resolves (i.e., we're inside container network)
    try:
        socket.gethostbyname(hostname)
        # Hostname resolves, we're in container network - no changes needed
        return
    except socket.gaierror:
        # Hostname doesn't resolve - we're running locally
        external_port = os.environ.get(
            "POSTGRES_EXTERNAL_PORT", os.environ.get("POSTGRES_PORT", "5432")
        )
        # Replace container hostname with localhost and optionally fix port
        new_url = database_url.replace(f"@{hostname}:", "@localhost:")
        if port != external_port:
            new_url = new_url.replace(f"@localhost:{port}/", f"@localhost:{external_port}/")
        os.environ["DATABASE_URL"] = new_url

fix_database_url()

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session, init_db
from backend.models.event import Event
from backend.models.llm_interaction import LLMInteraction


async def get_pipeline_status(pid: int) -> dict:
    """Get status of the seed script process."""
    try:
        proc = psutil.Process(pid)
        return {
            "running": proc.is_running(),
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_mb": proc.memory_info().rss / 1024 / 1024,
            "runtime": str(datetime.now(UTC) - datetime.fromtimestamp(proc.create_time(), UTC)),
        }
    except psutil.NoSuchProcess:
        return {"running": False, "error": "Process not found"}


async def get_reasoning_performance() -> dict:
    """Query database for reasoning performance metrics."""
    async with get_session() as session:
        # Get recent events (last hour)
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        
        # Count total events
        total_result = await session.execute(
            select(func.count(Event.id)).where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
            )
        )
        total_events = total_result.scalar() or 0
        
        if total_events == 0:
            return {
                "total_events": 0,
                "events_with_reasoning": 0,
                "avg_risk_score": None,
                "reasoning_stats": None,
            }
        
        # Count events with reasoning
        reasoning_result = await session.execute(
            select(func.count(Event.id)).where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
                Event.reasoning.isnot(None),
            )
        )
        events_with_reasoning = reasoning_result.scalar() or 0
        
        # Get risk score statistics
        risk_stats_result = await session.execute(
            select(
                func.avg(Event.risk_score).label("avg_risk"),
                func.min(Event.risk_score).label("min_risk"),
                func.max(Event.risk_score).label("max_risk"),
                func.count(Event.id).label("count"),
            ).where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
                Event.risk_score.isnot(None),
            )
        )
        risk_stats = risk_stats_result.first()
        
        # Get reasoning length statistics (for events with reasoning)
        reasoning_length_result = await session.execute(
            select(
                func.avg(func.length(Event.reasoning)).label("avg_length"),
                func.min(func.length(Event.reasoning)).label("min_length"),
                func.max(func.length(Event.reasoning)).label("max_length"),
            ).where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
                Event.reasoning.isnot(None),
            )
        )
        reasoning_length = reasoning_length_result.first()
        
        # Get risk level distribution
        risk_level_result = await session.execute(
            select(
                Event.risk_level,
                func.count(Event.id).label("count"),
            ).where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
                Event.risk_level.isnot(None),
            ).group_by(Event.risk_level)
        )
        risk_level_dist = {row.risk_level: row.count for row in risk_level_result}
        
        # Get LLM interaction performance (if available)
        llm_perf_result = await session.execute(
            select(
                func.avg(LLMInteraction.response_time_ms).label("avg_response_ms"),
                func.min(LLMInteraction.response_time_ms).label("min_response_ms"),
                func.max(LLMInteraction.response_time_ms).label("max_response_ms"),
                func.count(LLMInteraction.id).label("count"),
            ).where(
                LLMInteraction.created_at >= cutoff,
            )
        )
        llm_perf = llm_perf_result.first()
        
        # Get recent events with details
        recent_events_result = await session.execute(
            select(Event)
            .where(
                Event.started_at >= cutoff,
                Event.deleted_at.is_(None),
            )
            .order_by(Event.started_at.desc())
            .limit(10)
        )
        recent_events = recent_events_result.scalars().all()
        
        return {
            "total_events": total_events,
            "events_with_reasoning": events_with_reasoning,
            "reasoning_percentage": (events_with_reasoning / total_events * 100) if total_events > 0 else 0,
            "risk_score_stats": {
                "avg": round(risk_stats.avg_risk, 2) if risk_stats.avg_risk else None,
                "min": risk_stats.min_risk,
                "max": risk_stats.max_risk,
                "count": risk_stats.count,
            } if risk_stats else None,
            "reasoning_length_stats": {
                "avg_chars": round(reasoning_length.avg_length, 0) if reasoning_length.avg_length else None,
                "min_chars": reasoning_length.min_length,
                "max_chars": reasoning_length.max_length,
            } if reasoning_length else None,
            "risk_level_distribution": risk_level_dist,
            "llm_performance": {
                "avg_response_ms": round(llm_perf.avg_response_ms, 2) if llm_perf.avg_response_ms else None,
                "min_response_ms": llm_perf.min_response_ms,
                "max_response_ms": llm_perf.max_response_ms,
                "interaction_count": llm_perf.count,
            } if llm_perf and llm_perf.count > 0 else None,
            "recent_events": [
                {
                    "id": str(e.id),
                    "camera_id": e.camera_id,
                    "risk_score": e.risk_score,
                    "risk_level": e.risk_level,
                    "has_reasoning": e.reasoning is not None,
                    "reasoning_length": len(e.reasoning) if e.reasoning else 0,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                }
                for e in recent_events
            ],
        }


async def monitor_loop(pid: int, interval: int = 30):
    """Main monitoring loop."""
    print(f"Monitoring seed script (PID: {pid}) and database reasoning performance")
    print(f"Update interval: {interval} seconds")
    print("=" * 80)
    
    iteration = 0
    
    while True:
        iteration += 1
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        print(f"\n[{timestamp}] Update #{iteration}")
        print("-" * 80)
        
        # Check pipeline status
        pipeline_status = await get_pipeline_status(pid)
        print("\n📊 Pipeline Status:")
        if pipeline_status.get("running"):
            print(f"  ✓ Process running")
            print(f"  CPU: {pipeline_status.get('cpu_percent', 0):.1f}%")
            print(f"  Memory: {pipeline_status.get('memory_mb', 0):.1f} MB")
            print(f"  Runtime: {pipeline_status.get('runtime', 'N/A')}")
        else:
            print(f"  ✗ Process not running")
            if "error" in pipeline_status:
                print(f"  Error: {pipeline_status['error']}")
            print("\n⚠️  Seed script has completed or exited")
            break
        
        # Get database metrics
        print("\n📈 Database Reasoning Performance:")
        try:
            db_metrics = await get_reasoning_performance()
            
            print(f"  Total Events: {db_metrics['total_events']}")
            print(f"  Events with Reasoning: {db_metrics['events_with_reasoning']} ({db_metrics['reasoning_percentage']:.1f}%)")
            
            if db_metrics['risk_score_stats']:
                rs = db_metrics['risk_score_stats']
                print(f"\n  Risk Score Statistics:")
                print(f"    Average: {rs['avg']}")
                print(f"    Range: {rs['min']} - {rs['max']}")
                print(f"    Count: {rs['count']}")
            
            if db_metrics['reasoning_length_stats']:
                rl = db_metrics['reasoning_length_stats']
                print(f"\n  Reasoning Length Statistics:")
                print(f"    Average: {rl['avg_chars']:.0f} characters")
                print(f"    Range: {rl['min_chars']} - {rl['max_chars']} characters")
            
            if db_metrics['risk_level_distribution']:
                print(f"\n  Risk Level Distribution:")
                for level, count in sorted(db_metrics['risk_level_distribution'].items()):
                    print(f"    {level}: {count}")
            
            if db_metrics['llm_performance']:
                llm = db_metrics['llm_performance']
                print(f"\n  LLM Performance:")
                print(f"    Average Response Time: {llm['avg_response_ms']:.0f} ms")
                print(f"    Range: {llm['min_response_ms']} - {llm['max_response_ms']} ms")
                print(f"    Total Interactions: {llm['interaction_count']}")
            
            if db_metrics['recent_events']:
                print(f"\n  Recent Events (last 10):")
                for event in db_metrics['recent_events'][:5]:  # Show first 5
                    reasoning_indicator = "✓" if event['has_reasoning'] else "✗"
                    print(f"    [{reasoning_indicator}] Event {event['id'][:8]}... | "
                          f"Risk: {event['risk_score']} ({event['risk_level']}) | "
                          f"Reasoning: {event['reasoning_length']} chars")
        
        except Exception as e:
            print(f"  ✗ Error querying database: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)
        print(f"Waiting {interval} seconds for next update...")
        
        await asyncio.sleep(interval)


async def main():
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python monitor-pipeline-db.py <PID> [interval_seconds]")
        sys.exit(1)
    
    pid = int(sys.argv[1])
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    # Initialize database
    await init_db()
    
    try:
        await monitor_loop(pid, interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        from backend.core.database import close_db
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
