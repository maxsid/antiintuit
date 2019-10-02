import argparse

__all__ = [
    "config"
]


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Telegram Bot")
    parser.add_argument("--host", type=str, help="The host address to the antiintuit api server. "
                                                 "Required but can be specified by --host-file")
    parser.add_argument("--host-file", type=argparse.FileType("r"), help="The path to the file contains "
                                                                         "an address of the API server")
    parser.add_argument("--token", "-t", type=str, help="Telegram Bot Token. "
                                                        "Required but can be specified by --token-file.")
    parser.add_argument("--token-file", "-f", type=argparse.FileType("r"), help="The path to the file contains "
                                                                                "Telegram Bot Token")
    parser.add_argument("--img-path", default="image", type=str, help="The path in url between a host address and "
                                                                      "an image name")
    parser.add_argument("--redis-host", type=str, help="The host address to redis server")
    parser.add_argument("--redis-host-file", type=argparse.FileType("r"),
                        help="The file contains the host address to redis server")
    parser.add_argument("--redis-port", type=int, help="The host address to redis server", default=6379)
    parser.add_argument("--redis-port-file", type=argparse.FileType("r"),
                        help="The file contains the host address to redis server")
    config = parser.parse_args()

    actions_dict = dict(map(lambda ac: (ac.dest, ac), parser._actions))
    file_actions = filter(lambda dest: dest.endswith("_file") and dest[:-5] in actions_dict, actions_dict)
    for dest, file_dest in map(lambda dest: (dest[:-5], dest), file_actions):
        config_dest, config_dest_file = getattr(config, dest, None), getattr(config, file_dest, None)
        assert config_dest is not None or config_dest_file is not None, "The {} is not specified via {} or {}.".format(
            dest, actions_dict[dest].option_strings[0], actions_dict[file_dest].option_strings[0])
        if config_dest is None or config_dest_file is not None:
            setattr(config, dest, actions_dict[dest].type(config_dest_file.read()))
    return config


config = parse_arguments()
