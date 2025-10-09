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


def is_true(str_value: str | None) -> bool:
    if (str_value and (str_value.lower() == "true"
                       or str_value == "1"
                       or str_value.lower() == "y"
                       or str_value.lower() == "yes")):
        return True
    return False
