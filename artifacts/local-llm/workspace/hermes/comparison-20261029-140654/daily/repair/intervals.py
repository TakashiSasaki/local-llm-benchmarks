def merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals)
    result = []
    for start, end in ordered:
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result
