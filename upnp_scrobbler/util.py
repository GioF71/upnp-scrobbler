import datetime
import socket
import re


_print = print


def print(*args, **kw):
    _print("[%s]" % (datetime.datetime.now()), *args, **kw)


def duration_str_to_sec(duration: str) -> float:
    # print(f"duration_str_to_sec duration=[{duration}] ...")
    by_dot: list[str] = duration.split(".")
    len_by_dot: int = len(by_dot) if by_dot else 0
    if len_by_dot == 0 or len_by_dot > 2:
        if len_by_dot > 2:
            print(f"Duration split by [.] resulting in more [{len_by_dot}] elements (more than 2).")
        return float(0)
    # print(f"duration_str_to_sec duration=[{duration}] -> by_dot:[{by_dot}] ...")
    if len_by_dot == 1:
        # so we have one string after splitting by "."
        one_segment: str = by_dot[0]
        # case 1, no ":" -> "millis"
        if ":" not in one_segment:
            millis = one_segment
            left = ""
        # case 2, we have ":" -> "hh:mm:ss"
        else:
            millis = ""
            left = one_segment
    else:
        # we should be dealing with hh:mm:ss.nnn
        left = by_dot[0]
        millis = by_dot[1]
    # print(f"duration_str_to_sec duration=[{duration}] -> left:[{left}] millis:[{millis}]...")
    left_split: list[str] = left.split(":") if left else list()
    left_split_len: int = len(left_split)
    if left_split_len > 3:
        print(f"Left part [{left}] splitted by "":"" in {left_split_len} elements (more than 3)")
        return float(0)
    # seconds is last, if available
    milliseconds: float = float(int(millis)) if millis and len(millis) > 0 else float(0)
    seconds_str: str = left_split[left_split_len - 1] if left_split_len > 0 else "0"
    minutes_str: str = left_split[len(left_split) - 2] if left_split_len > 1 else "0"
    hours_str = left_split[left_split_len - 3] if left_split_len > 2 else "0"
    # print(f"duration_str_to_sec duration=[{duration}] -> "
    #       f"h:[{hours_str}] "
    #       f"m:[{minutes_str}] "
    #       f"s:[{seconds_str}] "
    #       f"millis:[{millis}] ...")
    result: float = ((milliseconds / 1000.0) +
                     float(int(seconds_str)) +
                     float(int(minutes_str) * 60.0) +
                     float(int(hours_str) * 3600.0))
    # print(f"duration_str_to_sec [{duration}] -> [{result}] (sec)")
    return result


def is_true(v: str | bool | None) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return bool(v)
    if (v.lower() == "true"
        or v == "1"
            or v.lower() == "y"
            or v.lower() == "yes"):
        return True
    return False


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    current_ip: str = None
    try:
        # doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        current_ip = s.getsockname()[0]
    except Exception:
        current_ip = '127.0.0.1'
    finally:
        s.close()
    return current_ip


def to_alphanumeric(v: str):
    alpha_and_digits: str = "[^a-zA-Z0-9]+"
    clean: str = re.sub(alpha_and_digits, " ", v)
    return " ".join(list(map(lambda x: x.strip(), clean.split(" "))))


def joined_words(s: str) -> str:
    return to_alphanumeric(s)


def joined_words_lower(s: str) -> str:
    return joined_words(s).lower()
