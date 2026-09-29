# Пакеты каталога

Каталог Control Plane — типы задач и артефактов, роли, capabilities, скиллы,
правила вывода работы, процессы, календари, описания агентов и правила уведомлений —
хранится в git пакетами: каталог `packages/<ключ>/` с `package.yaml` и YAML-файлами
объектов в обёртке `{apiVersion, kind, key, spec}`. Схема объектов —
[schema/v1/object.schema.json](schema/v1/object.schema.json), схема тестов процессов —
[schema/v1/test.schema.json](schema/v1/test.schema.json).

Какие пакеты ставить в инсталляцию, говорит файл установки
[deploy/packages.yaml](../deploy/packages.yaml). Инструмент — `tools/cp_packages.py`:

```bash
make packages-check                                  # проверка без стенда
make packages-plan  SERVER=http://taimen.localhost   # что изменится в живом Control Plane
make packages-apply SERVER=http://taimen.localhost   # применить
python3 tools/cp_packages.py --help                  # test, export, migrate-expr и остальное
```

Токен для `plan` и `apply` — переменная `CP_TOKEN` (access token audience
`control-plane`) или credential оператора, если инструмент запущен интерпретатором
установленного пакета control-plane. [example](example/) — минимальный пакет-образец.
Подробно — руководство, раздел «Пакеты каталога», и статьи о правилах вывода работы
и процессах.
