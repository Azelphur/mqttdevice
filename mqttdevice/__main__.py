from __future__ import annotations

import asyncio
import logging
from math import e
import yaml

from mqttdevice.device import Device

logger = logging.getLogger("mqttdevice")
logging.basicConfig(level=logging.INFO)

async def main(args):
    config = yaml.safe_load(args.config)
    device = Device(config)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(device.loop())
        for entity in device.entities.values():
            tg.create_task(entity.loop())

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="./config.yaml",
        help="Config file",
        type=argparse.FileType("r"),
        required=False,
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    asyncio.run(main(args))

    