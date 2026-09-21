import json
from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.core.config import settings


class KafkaBus:
    def __init__(self, bootstrap_servers: str | None = None) -> None:
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers

    async def publish(self, topic: str, payload: dict) -> None:
        producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(topic, json.dumps(payload).encode("utf-8"))
        finally:
            await producer.stop()

    async def consume(self, topic: str, group_id: str) -> AsyncIterator[dict]:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="latest",
        )
        await consumer.start()
        try:
            async for message in consumer:
                yield json.loads(message.value.decode("utf-8"))
        finally:
            await consumer.stop()

