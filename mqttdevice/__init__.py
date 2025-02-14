from __future__ import annotations

import logging
import yaml

from mqttdevice.device import MQTTDevice

logger = logging.getLogger("mqttdevice")
logging.basicConfig(level=logging.INFO)


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

    config = yaml.safe_load(args.config)
    m = MQTTDevice(config)
    m.loop_forever()
