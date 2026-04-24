from __future__ import annotations

import datetime
import os
from typing import Any, Optional, Callable

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

JSONRPCMessage = Any
StreamId = str
EventId = str
EventCallback = Callable[[Any], Any]


class MongoEventStore:
    """Simple MongoDB-backed event store for FastMCP session persistence.

    This implementation is intentionally lightweight and defensive: it accepts
    arbitrary JSON-RPC message objects (attempting to call .model_dump() when
    available) and stores them in a MongoDB collection with indexes for
    efficient replay by stream_id and timestamp.

    Usage:
      store = MongoEventStore()
      await store.store_event(stream_id, message)
      await store.replay_events_after(last_event_id, send_callback)

    Configuration via env:
      MONGO_URL, MONGO_DATABASE, MCP_EVENT_COLLECTION
    """

    def __init__(
        self,
        connection_string: str | None = None,
        database_name: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.connection_string = connection_string or os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self.database_name = database_name or os.getenv("MONGO_DATABASE", "mcp_sessions")
        self.collection_name = collection_name or os.getenv("MCP_EVENT_COLLECTION", "events")
        self._client: Optional[AsyncIOMotorClient] = None
        self._collection: Optional[AsyncIOMotorCollection] = None

    async def _ensure_connection(self) -> None:
        """Ensure MongoDB connection and collection are available and indexed."""
        if self._client is None:
            self._client = AsyncIOMotorClient(self.connection_string)
            self._collection = self._client[self.database_name][self.collection_name]

            # Create useful indexes for replay and lookup
            # stream_id + event_id for fast lookups, and stream_id + timestamp for range queries
            await self._collection.create_index([("stream_id", 1), ("event_id", 1)])
            await self._collection.create_index([("stream_id", 1), ("timestamp", 1)])

    async def store_event(self, stream_id: StreamId, message: JSONRPCMessage) -> EventId:
        """Store an event into MongoDB and return a generated event id."""
        await self._ensure_connection()
        # create a new ObjectId as event id
        event_id = str(ObjectId())

        # try to serialize message: prefer .model_dump, then dict, else fallback to str
        if hasattr(message, "model_dump"):
            try:
                message_dict = message.model_dump(by_alias=True, exclude_none=True)
            except Exception:
                message_dict = getattr(message, "__dict__", str(message))
        else:
            if isinstance(message, dict):
                message_dict = message
            else:
                message_dict = getattr(message, "__dict__", str(message))

        event_doc = {
            "_id": ObjectId(event_id),
            "stream_id": stream_id,
            "event_id": event_id,
            "message": message_dict,
            "timestamp": datetime.datetime.utcnow(),
            "message_type": getattr(message, "__class__", type(message)).__name__,
        }

        await self._collection.insert_one(event_doc)
        return event_id

    async def replay_events_after(self, last_event_id: EventId, send_callback: EventCallback) -> Optional[StreamId]:
        """Replay events after the given event id by calling send_callback for each.

        If last_event_id is not found, return None.
        """
        await self._ensure_connection()

        last_event = await self._collection.find_one({"event_id": last_event_id})
        if not last_event:
            return None

        query = {"stream_id": last_event["stream_id"], "timestamp": {"$gt": last_event["timestamp"]}}
        cursor = self._collection.find(query).sort("timestamp", 1)

        stream_id: Optional[StreamId] = None
        async for event_doc in cursor:
            message_dict = event_doc.get("message")
            # The FastMCP send callback expects an EventMessage-like object; instead
            # we'll pass a simple dict container that the callback can handle. If the
            # callback expects a more specific type, this may need adapting.
            event_message = {"message": message_dict, "event_id": event_doc.get("event_id")}
            await send_callback(event_message)
            if stream_id is None:
                stream_id = event_doc.get("stream_id")

        return stream_id

    async def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._collection = None

