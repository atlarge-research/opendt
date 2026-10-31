# kafka-init

Creates and configures Kafka topics before application services start.

- `kafka_init/main.py` - the topics of the configuration, with their retention and compaction

What it reads and writes, its settings, and its logs: [kafka-init in the docs](https://atlarge-research.github.io/opendt/docs/services/kafka) (in the repository,
`site/docs/services/kafka.md`). Its tests run with the others: `make test`.
