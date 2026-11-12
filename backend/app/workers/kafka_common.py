from confluent_kafka import Consumer, Producer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

from app.config import settings


def kafka_config() -> dict:
    if not settings.kafka_configured:
        raise RuntimeError("Kafka is not configured. Set KAFKA_BOOTSTRAP_SERVERS, KAFKA_USERNAME and KAFKA_PASSWORD in .env.")
    config = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": settings.kafka_sasl_mechanism,
        "sasl.username": settings.kafka_username,
        "sasl.password": settings.kafka_password,
        "client.id": "dayform-store",
        "socket.timeout.ms": 10000,
        "message.timeout.ms": 15000,
    }
    if settings.kafka_ca_path:
        config["ssl.ca.location"] = settings.kafka_ca_path
    return config


def create_producer() -> Producer:
    return Producer(kafka_config())


def create_consumer() -> Consumer:
    config = kafka_config()
    config.update({
        "group.id": settings.kafka_group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "session.timeout.ms": 45000,
        "max.poll.interval.ms": 300000,
    })
    return Consumer(config)


def ensure_topic() -> None:
    admin = AdminClient(kafka_config())
    futures = admin.create_topics([NewTopic(settings.kafka_topic, num_partitions=3, replication_factor=1)])
    for _, future in futures.items():
        try:
            future.result(timeout=12)
        except Exception as exc:
            # Kafka reports TopicAlreadyExistsError for an already provisioned topic.
            error_code = exc.args[0].code() if getattr(exc, "args", None) and hasattr(exc.args[0], "code") else None
            if error_code != KafkaError.TOPIC_ALREADY_EXISTS and "already exists" not in str(exc).lower():
                raise
