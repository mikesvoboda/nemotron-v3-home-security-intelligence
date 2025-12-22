"""Example usage of Redis client in the home security intelligence system."""

import asyncio
from datetime import datetime

from backend.core.redis import RedisClient


async def example_queue_operations():
    """Demonstrate queue operations for batch processing."""
    print("\n=== Queue Operations Example ===")

    client = RedisClient()
    await client.connect()

    try:
        queue_name = "example_detections_queue"

        # Clear any existing data
        await client.clear_queue(queue_name)

        # Simulate adding detection events to queue
        print("\n1. Adding detections to queue...")
        for i in range(5):
            detection = {
                "id": i + 1,
                "camera_id": 1,
                "timestamp": datetime.now().isoformat(),
                "objects": ["person", "car"],
            }
            length = await client.add_to_queue(queue_name, detection)
            print(f"   Added detection {i+1}, queue length: {length}")

        # Check queue length
        length = await client.get_queue_length(queue_name)
        print(f"\n2. Current queue length: {length}")

        # Peek at items without removing
        print("\n3. Peeking at first 3 items...")
        items = await client.peek_queue(queue_name, start=0, end=2)
        for item in items:
            print(f"   - Detection {item['id']}: {item['objects']}")

        # Process items from queue
        print("\n4. Processing items from queue...")
        while True:
            item = await client.get_from_queue(queue_name, timeout=1)
            if not item:
                break
            print(f"   Processing detection {item['id']}")

        # Verify queue is empty
        length = await client.get_queue_length(queue_name)
        print(f"\n5. Queue length after processing: {length}")

    finally:
        await client.disconnect()


async def example_pubsub():
    """Demonstrate pub/sub for real-time event broadcasting."""
    print("\n=== Pub/Sub Example ===")

    publisher = RedisClient()
    await publisher.connect()

    subscriber = RedisClient()
    await subscriber.connect()

    try:
        channel = "example_events"

        # Subscribe to channel
        print(f"\n1. Subscribing to channel '{channel}'...")
        pubsub = await subscriber.subscribe(channel)

        # Create a task to listen for messages
        async def listen_for_messages():
            print("   Listening for messages...")
            count = 0
            async for message in subscriber.listen(pubsub):
                print(f"   Received: {message['data']}")
                count += 1
                if count >= 3:
                    break

        listener_task = asyncio.create_task(listen_for_messages())

        # Give subscriber time to connect
        await asyncio.sleep(0.5)

        # Publish some messages
        print("\n2. Publishing messages...")
        for i in range(3):
            event = {
                "type": "motion_detected",
                "camera_id": i + 1,
                "timestamp": datetime.now().isoformat(),
            }
            subscribers = await publisher.publish(channel, event)
            print(f"   Published event to {subscribers} subscriber(s)")
            await asyncio.sleep(0.1)

        # Wait for listener to finish
        await listener_task

        # Unsubscribe
        await subscriber.unsubscribe(channel)
        print(f"\n3. Unsubscribed from channel '{channel}'")

    finally:
        await publisher.disconnect()
        await subscriber.disconnect()


async def example_cache_operations():
    """Demonstrate cache operations for temporary data storage."""
    print("\n=== Cache Operations Example ===")

    client = RedisClient()
    await client.connect()

    try:
        # Set camera status in cache
        print("\n1. Setting camera status in cache...")
        camera_id = 1
        status = {
            "online": True,
            "fps": 30,
            "resolution": "1920x1080",
            "last_seen": datetime.now().isoformat(),
        }
        await client.set(f"camera:{camera_id}:status", status, expire=300)
        print(f"   Cached status for camera {camera_id} (expires in 300s)")

        # Get cached status
        print("\n2. Retrieving cached status...")
        cached_status = await client.get(f"camera:{camera_id}:status")
        print(f"   Camera {camera_id} status: {cached_status}")

        # Check if key exists
        exists = await client.exists(f"camera:{camera_id}:status")
        print(f"\n3. Cache key exists: {exists}")

        # Delete cache key
        print("\n4. Deleting cache key...")
        deleted = await client.delete(f"camera:{camera_id}:status")
        print(f"   Deleted {deleted} key(s)")

        # Verify deletion
        cached_status = await client.get(f"camera:{camera_id}:status")
        print(f"   Status after deletion: {cached_status}")

    finally:
        await client.disconnect()


async def example_health_check():
    """Demonstrate health check functionality."""
    print("\n=== Health Check Example ===")

    client = RedisClient()

    # Check health before connection (should fail)
    print("\n1. Health check before connection:")
    try:
        health = await client.health_check()
        print(f"   Status: {health}")
    except RuntimeError as e:
        print(f"   Expected error: {e}")

    # Connect and check health
    print("\n2. Connecting to Redis...")
    await client.connect()

    print("\n3. Health check after connection:")
    health = await client.health_check()
    print(f"   Status: {health['status']}")
    print(f"   Connected: {health['connected']}")
    if "redis_version" in health:
        print(f"   Redis version: {health['redis_version']}")

    await client.disconnect()


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Redis Client Examples for Home Security Intelligence System")
    print("=" * 60)

    try:
        await example_health_check()
        await example_queue_operations()
        await example_cache_operations()
        await example_pubsub()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("\nMake sure Redis is running:")
        print("  docker run -d -p 6379:6379 redis:7-alpine")


if __name__ == "__main__":
    asyncio.run(main())
