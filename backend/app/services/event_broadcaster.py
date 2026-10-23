import threading
from collections import defaultdict
from collections.abc import Iterator
from queue import Empty, Queue


class EventBroadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, set[Queue]] = defaultdict(set)

    def subscribe(self, room_id: str) -> Queue:
        queue: Queue = Queue()
        with self._lock:
            self._subscribers[room_id].add(queue)
        return queue

    def unsubscribe(self, room_id: str, queue: Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(room_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(room_id, None)

    def publish(self, room_id: str, event: str, data: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(room_id, ()))
        for queue in subscribers:
            queue.put((event, data))

    def iter_events(self, queue: Queue) -> Iterator[str]:
        while True:
            try:
                event, data = queue.get(timeout=15)
            except Empty:
                yield ": keep-alive\n\n"
                continue
            yield f"event: {event}\ndata: {data}\n\n"


broadcaster = EventBroadcaster()
